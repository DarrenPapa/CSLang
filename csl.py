import re, sys, os, itertools, docus, typer
from _io import TextIOWrapper as FileObject
from pprint import pprint as pp
from copy import deepcopy

TOKENS = re.compile("(\[|\]|\(|\)|\<(?:.*?)\>|%\<[\w/\\\s]+\>|-?\d+\.\.-?\d+|\#(?:.*?)\#|\"(?:.*?)\"|-?\d+\.\d+|\;|-?\d+|[!~]?[@\.\w\\\/_]+(?:[\d]+)?)", re.DOTALL)

cli = typer.Typer()

PRESET_METADATA = {
    "version":0.1
}

PRESET_CONS = {
    "true":1,
    "false":0,
    "no_value":0, # no_value IS REAL NONE
    "none":"0",   # none IS NOT THE REAL NONE because it represents NaN or in this case NaV (not a value)
    "last":-1,
    "first":0
}

CHARS = {
    "%~~":"~~%",
    "~~newline":"\n",
    "~~tab":"\t",
    "~~bell":"\b",
    "~~return":"\r",
    "~~null":"\0",
    "~~%":"~~"
}

VER = 0.1

BINDIR = os.path.join(os.path.dirname(sys.argv[0]),"")
LIBDIR = os.path.join(BINDIR,"libs","")
LOCALS = os.path.join(os.getcwd(),"")

if not os.path.isdir(LIBDIR):
    os.mkdir(LIBDIR)

def cindex(string, search):
    if search not in string:
        return
    return string.index(search)+len(search)-1

def flatten_dict(d, parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def tokenize(code):
    result = []
    stack = []

    for item in TOKENS.findall(code):
        if item == "[":
            stack.append(result)
            result = []
        elif item == "]":
            if stack:
                outer = stack.pop()
                outer.append(result)
                result = outer
        elif item == "(":
            stack.append(result)
            result = []
        elif item == ")":
            if stack:
                outer = stack.pop()
                outer.append(tuple(result))
                result = outer
        else:
            if item.startswith('"') and item.endswith('"'):
                k = item[1:-1]
                for s, c in CHARS.items():
                    k = k.replace(s,c)
                result.append(k)
            elif item.startswith('<') and item.endswith('>'):
                result.append(item[1:-1])
            elif item.startswith('%<') and item.endswith('>'):
                result.append(LIBDIR+item[2:-1])
            elif item.startswith('#') and item.endswith('#'):
                continue
            elif re.fullmatch("-?\d+\.\d+", item):
                result.append(float(item))
            elif re.fullmatch("-?\d+", item):
                result.append(int(item))
            elif (m:=re.fullmatch("-?\d+\.\.-?\d+",item)):
                m = list(map(int,m[0].split('..')))
                k = list(range(*m))
                result.append(k if m[0] < m[1] else [])
                del m, k
            else:
                result.append(item)
    if stack:
        print('Error: Syntax: Missing "]" or ")"')
        return []
    return result

def custom_hash(string):
    k = 1
    for char in string:
        k += (ord(char)+k) << (ord(char)%k) + 45
    return k + 26252009

def rec_get(obj, path, sep="."):
    name, *path = path.split(".")
    if path:
        if name in obj:
            n_obj = obj[name]
            if isinstance(n_obj, dict):
                return rec_get(n_obj, ".".join(path))
            else:
                return "0"
        return "0"
    else:
        if name in obj:
            return obj[name]
        else:
            return "0"

def rec_set(obj, path, value, sep="."):
    name, *path = path.split(".")
    if path:
        if name in obj:
            n_obj = obj[name]
            if isinstance(n_obj, dict):
                return rec_set(n_obj, ".".join(path),value)
        else:
            obj[name] = {}
            n_obj = obj[name]
            if isinstance(n_obj, dict):
                return rec_set(n_obj, ".".join(path),value)
    else:
         obj[name] = value

def rec_pop(obj, path, sep="."):
    name, *path = path.split(".")
    if path:
        if name in obj:
            n_obj = obj[name]
            if isinstance(n_obj, dict):
                return rec_pop(n_obj, ".".join(path))
        else:
            obj[name] = {}
            n_obj = obj[name]
            if isinstance(n_obj, dict):
                return rec_pop(n_obj, ".".join(path))
    else:
         if name in obj:
             return obj.pop(name)

def eat(code):
    if not code:
        return None
    if ";" not in code:
        return ["err","Syntax: Missing `;`!"],None
    i = code.index(";")
    item, rest = code[:i],code[i+1:]
    if not item and not rest:
        return None
    else:
        return item, (rest if len(rest) else None)

def replace_list(vlist, data, form="{name}", callback=None):
    for pos,item in enumerate(vlist):
        if type(item) == list:
            vlist[pos] = replace_list(item, data)
        elif callback and item == form.format(name=item):
            vlist[pos] = callback(data, item)
        elif item in data:
            if vlist[pos] == form.format(name=item):
                vlist[pos] = data[item]
    return vlist

def lvar(vlist, data):
    for pos,item in enumerate(vlist):
        if type(item) == list:
            vlist[pos] = replace_list(item, data)
        elif not isinstance(item, str):
            continue
        elif item.startswith('@'):
            vlist[pos] = rec_get(data, item[1:])
    return vlist

def lvarg(vlist, data):
    for pos,item in enumerate(vlist):
        if type(item) == list:
            vlist[pos] = replace_list(item, data)
        elif not isinstance(item, str):
            continue
        elif item.startswith('g@'):
            vlist[pos] = rec_get(data, item[2:])
    return vlist

def lvart(vlist, data):
    for pos,item in enumerate(vlist):
        if type(item) == list:
            vlist[pos] = replace_list(item, data)
        elif not isinstance(item, str):
            continue
        elif item.startswith('t@'):
            t = type(rec_get(data, item[2:])).__name__
            if t == "str":
                vlist[pos] = "string"
            else:
                vlist[pos] = t
    return vlist

def lvartg(vlist, data):
    for pos,item in enumerate(vlist):
        if type(item) == list:
            vlist[pos] = replace_list(item, data)
        elif not isinstance(item, str):
            continue
        elif item.startswith('t.g@'):
            t = type(rec_get(data, item[4:])).__name__
            if t == "str":
                vlist[pos] = "string"
            else:
                vlist[pos] = t
    return vlist

def join(*names):
    if len(names) == 1:
        return names[0]
    elif len(names) == 0:
        return "root.attr.temp"
    name = names[0]
    for n in map(str,names[1:]):
        if n.startswith('.'):
            name += n
        else:
            name += "." + n
    return name

def conv_list(lt,r=0):
    for pos, item in enumerate(lt):
        if isinstance(item, (int, float)):
            lt[pos] = str(item)
        elif isinstance(item, str):
            lt[pos] = f'"{item}"'
        elif isinstance(item, list):
            temp = conv_list(item,r=r+1)
            lt[pos] = "[" + " ".join(temp) + "]"
        elif isinstance(item, tuple):
            temp = conv_tup(item,r=r+1)
            lt[pos] = "(" + " ".join(temp) + ")"
    return lt if r != 0 else "[" + " ".join(lt) + "]"

def conv_tup(lt,r=0):
    lt = list(lt)
    for pos, item in enumerate(lt):
        if isinstance(item, (int, float)):
            lt[pos] = str(item)
        elif isinstance(item, str):
            lt[pos] = f'"{item}"'
        elif isinstance(item, list):
            temp = conv_list(item,r=r+1)
            lt[pos] = "[" + " ".join(temp) + "]"
        elif isinstance(item, tuple):
            temp = conv_list(item,r=r+1)
            lt[pos] = "(" + " ".join(temp) + ")"
    return tuple(lt) if r != 0 else "(" + " ".join(lt) + ")"

def sstr(s,n=20):
    if n < 0:
        return 'Too large!'
    k = str(s)
    return k[:n]+"..." if len(k) >= n else k

def pdict(d,id=0,sid="    "):
    for n, i in d.items():
        if isinstance(i,dict):
            print(sid*id+n)
            pdict(i,id=id+1,sid=sid) if i else print(sid*(id+1)+"[No content]")
        else:
            print(sid*id+n+" : "+sstr(i,70-len(sid*id+n+" : ")))

class inter:
    def __init__(self,path,argv=None):
        self.data = {}
        self.path = path
        self.data.update({
            "const":PRESET_CONS.copy(),
            "meta":PRESET_METADATA.copy()
        })
        g = {
            "root":{
                "func":{},
                "attr":{
                    "path":path
                },
                "args":{f"argv{num}":v for num,v in enumerate(argv)} if argv != None else {},
                "argc": 0 if argv == None else len(argv)
            },
            "const":PRESET_CONS.copy(),
            "meta":PRESET_METADATA.copy()
        }
        self.scope = [g.copy()]
        del g
        self.lscope = self.scope[-1]
        self.gscope = self.scope[0]
    def new_scope(self):
        self.scope.append(self.data.copy())
        self.lscope = self.scope[-1]
    def pop_scope(self):
        if len(self.scope) > 1:
            self.scope.pop()
            self.lscope = self.scope[-1]
    def local_set(self, name, value):
        rec_set(self.lscope,name,value)
    def non_local_set(self, name, value):
        if len(self.scope) > 1:
            rec_set(self.scope[-2],name,value)
        else:
            rec_set(self.lscope,name,value)
    def non_local_get(self, name):
        if len(self.scope) > 1:
            return rec_get(self.scope[-2],name)
        else:
            return rec_get(self.lscope,name)
    def global_set(self, name, value):
        rec_set(self.gscope,name,value)
    def local_get(self, name, default="0"):
        k = rec_get(self.lscope, name)
        if k == "0":
            return default
        else:
            return k
    def global_get(self, name, default="0"):
        k = rec_get(self.gscope, name)
        if k == "0":
            return default
        else:
            return k
    def local_rem(self, name):
        return rec_pop(self.lscope, name)
    def global_rem(self, name):
        return rec_pop(self.gscope, name)
    def process_code(self,code):
        k = []
        if isinstance(code, str):
            code = tokenize(code)
        while True:
            line = eat(code)
            if line == None:
                break
            cline, code = line
            k.append(cline)
        return k[::-1]
    def run(self, code, path=None, bname="root", show_error=True):
        code = self.process_code(code)
        local_path = path if path else self.path
        while code:
            line = lvar(code.pop(), self.lscope)
            line = lvarg(line, self.gscope)
            line = lvart(line, self.lscope)
            line = lvartg(line, self.gscope)
            if not line:
                continue
            ins, *args = line
            types = tuple(map(type,args))
            atypes = tuple(map(type,line))
            argc = len(args)
            ## IO
            if ins == "println":
                print(*args)
            elif ins == "print":
                print(*args,end="")
            elif ins == "printf" and argc > 1 and types[0] == str and types[1:] == (str,)*(argc-1):
                text = args[0]
                for pos,vals in enumerate(map(self.local_get,args[1:])):
                    text = text.replace(f"%{pos}%",str(vals))
                    text = text.replace('%%',str(vals),1)
                for name in args[1:]:
                    text = text.replace(
                        f"%{name}%",
                        str(self.local_get(
                            name,self.global_get(name,f"<`{name}` Not Found>"
                        )))
                    )
                print(text)
                del name, text
            elif ins == "input" and argc == 2 and types == (str,str):
                self.local_set(args[0],input(args[1]))
            ## Require
            elif ins == "require_version" and argc == 1 and types == (float,):
                if VER < args[0]:
                    print(f'Version Error: Must have CSLang version `{args[0]}`!\nThe current version is `{VER}`') if show_error else None
                    break
            ## Stuff
            elif isinstance(ins, list) and argc == 0: # meep
                if self.run(ins,bname=bname,show_error=show_error):
                    break
            elif ins == "scope" and argc == 2 and types == (str,list): # for modules and clean scopes :33
                self.new_scope()
                self.local_set("export",{})
                if self.run(args[1],bname=args[0],show_error=show_error):
                    break
                shez = deepcopy(self.local_get("export",{}))
                self.pop_scope()
                self.local_set(args[0],shez)
                del shez
            elif atypes == (str, list) and argc == 2: # custom block
                self.new_scope()
                self.local_set("this",self.local_get(ins,{}))
                if self.run(args[0],bname=ins,show_error=show_error):
                    break
                shez = deepcopy(self.local_get("this",{}))
                self.pop_scope()
                self.local_set(ins,shez)
                del shez
            elif ins == "class" and types == (str, list) and argc == 2: # custom block
                self.new_scope()
                self.local_set("this",self.local_get(args[0],{}))
                if self.run(args[1],bname=args[0],show_error=show_error):
                    break
                shez = deepcopy(self.local_get("this",{}))
                self.pop_scope()
                self.local_set(args[0],shez)
                del shez
            ## Variables
            elif ins == "set" and argc == 2 and types[0] == str:
                name, val = args
                self.local_set(name, val)
                del name, val
            elif ins == "gset" and argc == 2 and types[0] == str:
                name, val = args
                self.global_set(name, val)
                del name, val
            elif ins == "nset" and argc == 2 and types[0] == str:
                name, val = args
                self.non_local_set(name, val)
                del name, val
            elif ins == "nget" and argc == 2 and types[0] == str:
                name, new_name = args
                self.local_set(new_name, self.non_local_get(name))
                del name, new_name
            elif ins == "object_set" and argc == 3 and types[:2] == (str,str):
                otype, name, val = args
                self.local_set(join(name,"value"), val)
                self.local_set(join(name,"type"), otype)
                self.local_set(join(name,"_from_"), bname)
                self.local_set(join(name,"_name_"), name)
                del name, val, otype
            elif ins == "object_gset" and argc == 3 and types[:2] == (str,str):
                otype, name, val = args
                self.global_set(join(name,"value"), val)
                self.global_set(join(name,"type"), otype)
                self.global_set(join(name,"_from_"), bname)
                self.global_set(join(name,"_name_"), name)
                del name, val, otype
            elif ins == "del" and argc == 1 and types[0] == str:
                self.local_rem(args[0])
            elif ins == "gdel" and argc == 1 and types[0] == str:
                self.global_rem(args[0])
            elif ins == "dir" and argc == 0:
                print(*self.lscope.keys(),sep=", ")
            elif ins == "fdir" and argc == 0:
                pdict(self.lscope)
            elif ins == "dir" and argc == 1 and types == (dict,):
                print(*args[0].keys(),sep=", ")
            elif ins == "dir" and argc == 1:
                print(args[0])
            elif ins == "pydir" and argc == 1:
                print(*dir(args[0]),sep=", ")
            elif ins == "unpack" and argc == 1 and types == (dict,):
                for keys, values in args[0].items():
                    self.local_set(keys, values)
                if args[0]:
                    del keys, values
            ## Error
            elif ins == "err" and argc == 1 and types == (str,):
                print("Error:",args[0]) if show_error else None
                break
            elif ins == "try" and argc == 2 and types == (list,list):
                if self.run(args[0],bname=bname,show_error=False):
                    if self.run(args[1],bname=bname):
                        print('Error: Handled an error but the error persisted.') if show_error else None
                        break
            ## Control flow
            elif ins == "stop":
                return 0
            ## Function
            elif ins == "def" and argc == 3 and types == (str,tuple,list):
                name, params, body = args
                self.global_set(join("root", "func", name), {"_params_":params, "_body_":body, "_doc_":"", "_name_":name, "_from_":bname})
                del name, params, body
            elif ins == "call" and argc == 2 and types == (str, tuple):
                fname, params = args
                k = self.global_get(join("root","func",fname))
                if k == "0":
                    print(f"Error: Call: Function `{fname}` does not exist!") if show_error else None
                    break
                if len(params) != len(k["_params_"]):
                    print("Error: Call: The arguments and parameters must match in quantity!") if show_error else None
                    break
                self.new_scope()
                for name, value in zip(k["_params_"],params):
                    self.local_set(name, value)
                if self.run(k["_body_"], bname=fname,show_error=show_error):
                    self.pop_scope()
                    print(f'Error: An error in the function `{fname}` occured!') if show_error else None
                    return 1
                self.pop_scope()
                del params, k, fname
            elif ins == "!method" and argc == 3 and types == (str,tuple,list):
                name, params, body = args
                cobj, name = name.split('.',1)
                if cobj not in self.lscope:
                    print(f'Error: Object `{cobj}` does not exist!') if show_error else None
                    break
                self.local_set(join(cobj, "_func_", name), {"_params_":params, "_body_":body, "_doc_":"", "_from_":cobj})
                del name, params, body, cobj
            elif ins == "!call" and argc == 2 and types == (str, tuple):
                fname, params = args
                cobj, fname = fname.split('.',1)
                k = self.local_get(join(cobj,"_func_",fname))
                if k == "0":
                    print(f"Error: Call: Function `{fname}` does not exist!") if show_error else None
                    break
                if len(params) != len(k["_params_"]):
                    print("Error: Call: The arguments and parameters must match in quantity!") if show_error else None
                    break
                self.new_scope()
                for name, value in zip(k["_params_"],params):
                    self.local_set(name, value)
                self.local_set("self", self.non_local_get(cobj))
                if self.run(k["_body_"], bname=join(cobj,fname),show_error=show_error):
                    self.pop_scope()
                    print(f'Error: An error in the method `{fname}` of object `{cobj}` occured!') if show_error else None
                    break
                self.non_local_set(cobj, self.local_get("self"))
                self.pop_scope()
                del params, k, fname, cobj
            elif ins == "bare_call" and argc == 2 and types == (dict, tuple):
                body, params = args
                k = body
                if "_params_" not in k or "_body_" not in k or "_name_" not in k:
                    del body, params, k
                    continue
                if k == "0":
                    print(f"Error: Call: Function `{k['_name_']}` does not exist!") if show_error else None
                    break
                if len(params) != len(k["_params_"]):
                    print("Error: Call: The arguments and parameters must match in quantity!") if show_error else None
                    break
                self.new_scope()
                for name, value in zip(k["_params_"],params):
                    self.local_set(name, value)
                if self.run(k["_body_"], bname=k["_name_"],show_error=show_error):
                    self.pop_scope()
                    break
                self.pop_scope()
                del params, k, body
            elif ins == "help" and argc == 1 and types == (str,):
                obj = self.global_get(join("root","func",args[0]), {
                    "_doc_":f"[{args[0]}]: Info not available",
                    "_params_":()
                })
                print(f"Paramaters for `{args[0]}`: ({', '.join(obj['_params_'])})\n  {obj['_doc_'].replace(chr(10),chr(10)+'  ')}")
                del obj
            elif ins == "!help" and argc == 1 and types == (str,):
                cobj, fname = args[0].split(".",1)
                obj = self.global_get(join(cobj,"_func_",fname), {
                    "_doc_":f"[{args[0]}]: Info not available",
                    "_params_":()
                })
                print(f"Paramaters for `{args[0]}`: ({', '.join(obj['_params_'])})\n  {obj['_doc_'].replace(chr(10),chr(10)+'  ')}")
                del cobj, fname, obj
            elif ins == "docu_help" and argc == 1 and types == (str,):
                docus.find_docu(args[0])
            elif ins == "docu_help" and argc == 0:
                print(docus.doc)
            elif ins == "return" and types == (str,)*argc:
                for name in args:
                    self.non_local_set(join(join("rets",bname),name), self.local_get(name))
            ## Saving
            elif ins == "pickle" and argc == 2 and types == (str, str):
                file, oname = args
                with open(file,"w") as temp:
                    for name, value in flatten_dict(self.local_get(oname,{})).items():
                        if isinstance(value, str):
                            value = f'"{value}"'
                        if isinstance(value, (str,int,float)):
                            temp.write(f"set {oname}.{name} {value};\n")
                        elif isinstance(value, list):
                            temp.write(f"set {oname}.{name} {conv_list(value)};\n")
                        elif isinstance(value, tuple):
                            temp.write(f"set {oname}.{name} {conv_tup(value)};\n")
                del file, temp, oname
            ## OOP
            elif ins == "object" and argc >= 1 and types[0] == str:
                name, attrs = args
                self.local_set(name,{"_from_":bname,"_name_":name})
                for attr in attrs:
                    self.local_set(join(name,attr),'0')
                del name, attrs
            elif ins == "new" and argc == 2 and types == (str,str):
                k = self.local_get(args[0])
                self.local_set(args[1],deepcopy(k))
                self.local_set(join(args[1],"_name_"),args[1])
                self.local_set(join(args[1],"_from_"),args[0])
            elif ins == "init_new" and argc == 3 and types == (str,str,tuple):
                k = self.local_get(args[0])
                self.local_set(args[1],deepcopy(k))
                self.local_set(join(args[1],"_name_"),args[1])
                self.local_set(join(args[1],"_from_"),args[0])
                k = self.local_get(join(args[1],"_func_","init"))
                if "init" not in self.local_get(join(args[1],"_func_")):
                    print(f"Error: Call: Function `init` of object `{args[1]}` does not exist!") if show_error else None
                    break
                if len(args[2]) != len(k["_params_"]):
                    print("Error: Call: The arguments and parameters must match in quantity!") if show_error else None
                    break
                self.new_scope()
                for name, value in zip(k["_params_"],args[2]):
                    self.local_set(name, value)
                self.local_set("self", self.non_local_get(args[1]))
                if self.run(k["_body_"], bname=f"{args[1]}.init",show_error=show_error):
                    self.pop_scope()
                    print(f"Error: While running the contructor of `{args[1]}`!") if show_error else None
                    return
                self.non_local_set(args[1], self.local_get("self"))
                self.pop_scope()
                del k
            elif ins == "delete" and argc == 1 and types == (str,):
                k = self.local_get(join(args[0],"_func_","_del_"))
                if "_del_" not in self.local_get(join(args[0],"_func_")):
                    print(f"Error: Call: Function `_del_` of object `{args[0]}` does not exist!") if show_error else None
                    break
                if k == "0":
                    print(f"Error Object `{args[0]}` does not exist!") if show_error else None
                    break
                self.new_scope()
                self.local_set("self", self.non_local_get(args[0]))
                if self.run(k["_body_"], bname=f"{args[0]}._del_",show_error=show_error):
                    self.pop_scope()
                    print(f"Error: While running the destroyer of `{args[0]}`!") if show_error else None
                    break
                self.pop_scope()
                self.local_rem(args[0])
                del k
            ## Module
            elif ins == "import" and argc == 1 and types == (str,):
                if not os.path.isfile(os.path.join(local_path,args[0])):
                    print("Error: Invalid path:",os.path.join(local_path,args[0])) if show_error else None
                    break
                lpath = os.path.dirname(os.path.join(local_path,args[0]))
                if self.run(open(os.path.join(local_path,args[0])).read(),path=lpath,bname=args[0],show_error=show_error):
                    print('Error: Error while importing:',os.path.join(local_path,args[0])) if show_error else None
                    break
                del lpath
            elif ins == "import_global" and argc == 1 and types == (str,):
                if not os.path.isfile(os.path.join(BINDIR,"libs",args[0])):
                    print("Error: Invalid path!") if show_error else None
                    break
                lpath = os.path.dirname(os.path.join(LIBDIR,args[0]))
                if self.run(open(os.path.join(BINDIR,"libs",args[0])).read(),path=lpath,bname=args[0],show_error=show_error):
                    print('Error: Error while importing!',os.path.join(LIBDIR,args[0])) if show_error else None
                    break
                del lpath
            elif ins == "import" and argc == 1 and types == (list,):
                for file in args[0]:
                    if not os.path.isfile(os.path.join(local_path,file)):
                        print("Error: Invalid path:",os.path.join(local_path,file)) if show_error else None
                        break
                    lpath = os.path.dirname(os.path.join(local_path,args[0]))
                    if self.run(open(os.path.join(local_path,file)).read(),path=lpath,bname=args[0],show_error=show_error):
                        print('Error: Error while importing:',os.path.join(local_path,file)) if show_error else None
                        break
                    del lpath
                else:
                    continue
                break
            elif ins == "import_global" and argc == 1 and types == (list,):
                for file in args[0]:
                    if not os.path.isfile(os.path.join(LIBDIR,file)):
                        print("Error: Invalid path:",os.path.join(LIBDIR,file)) if show_error else None
                        break
                    lpath = os.path.dirname(os.path.join(LIBDIR,file))
                    if self.run(open(os.path.join(BINDIR,"libs",file)).read(),path=lpath,bname=args[0],show_error=show_error):
                        print('Error: Error while importing:',os.path.join(LIBDIR,file)) if show_error else None
                        break
                    del lpath
                else:
                    continue
                break
            ## Math :((
            elif ins == "add" and argc ==  3 and types[0] == str and types[1:] in ((int,int),(int,float),(float,int),(float,float),(str,str)):
                self.local_set(args[0],args[1]+args[2])
            elif ins == "sub" and argc ==  3 and types[0] == str and types[1:] in ((int,int),(int,float),(float,int),(float,float)):
                self.local_set(args[0],args[1]-args[2])
            elif ins == "mul" and argc ==  3 and types[0] == str and types[1:] in ((int,int),(int,float),(float,int),(float,float),(str,int)):
                self.local_set(args[0],args[1]*args[2])
            elif ins == "div" and argc ==  3 and types[0] == str and types[1:] in ((int,int),(int,float),(float,int),(float,float)):
                self.local_set(args[0],args[1]/args[2])
            elif ins == "fdiv" and argc ==  3 and types[0] == str and types[1:] in ((int,int),(int,float),(float,int),(float,float)):
                self.local_set(args[0],args[1]//args[2])
            elif ins == "mod" and argc == 3 and types[0] == str and types[1:] == (int,int):
                self.local_set(args[0],args[1]%args[2])
            elif ins == "pow" and argc == 3 and types[0] == str and types[1:] == (int,int):
                self.local_set(args[0],args[1]**args[2])
            elif ins == "range" and argc == 2 and types == (str,int):
                self.local_set(args[0],list(range(args[1])))
            ## String
            elif ins == "get_str" and argc == 3 and types == (str, int, str):
                if args[1] not in range(len(args[0])):
                    print("Error: Invalid index!") if show_error else None
                    break
                self.local_set(args[2],args[0][args[1]])
            elif ins == "format" and argc > 2 and types[0] == str and types[1] == str and types[1:] == (str,)*(argc-1):
                text = args[1]
                for pos,vals in enumerate(map(self.local_get,args[2:])):
                    text = text.replace(f"%{pos}%",str(vals))
                    text = text.replace('%%',str(vals),1)
                for name in args[2:]:
                    text = text.replace(
                        f"%{name}%",
                        str(self.local_get(
                            name,self.global_get(name,f"<`{name}` Not Found>"
                        )))
                    )
                self.local_set(args[0],text)
                del name, text
            ## List
            elif ins == "new_list" and argc == 2 and types == (str,list):
                self.local_set(args[0],args[1])
            elif ins == "pop_list" and argc == 2 and types == (list, str):
                if not args[0]:
                    print('Error: Empty list!') if show_error else None
                    break
                self.local_set(args[1],args[0].pop())
            elif ins == "get_list" and argc == 3 and types == (list, int, str):
                if args[1] not in range(len(args[0])):
                    print("Error: Invalid index!") if show_error else None
                    break
                self.local_set(args[2],args[0][args[1]])
            elif ins == "set_list" and argc == 3 and types[:2] == (list, int):
                if args[1] not in range(len(args[0])):
                    print("Error: Invalid index!") if show_error else None
                    break
                args[0][args[1]] = args[2]
            elif ins == "append_list" and argc == 2 and types[0] == list:
                args[0].append(args[1])
            ## Str and List
            elif ins == "slice" and argc == 4 and types[0] in (str, list) and types[1:] == (int,int) and types[-1] == str:
                arr, pos0, pos1, name = args
                self.local_set(name, arr[pos0:pos1])
                del arr, pos0, pos1, name
            elif ins == "reverse" and argc == 2 and types[0] in (list, str) and types[1] == str:
                arr, name = args
                self.local_set(name, arr[::-1])
                del arr, name
            ## Loops
            elif ins == "foreach" and argc == 3 and types[0] == str and types[2] == list:
                for i in args[1]:
                    self.local_set(args[0],i)
                    if self.run(args[2],bname=bname+".loop"):
                        break
                else:
                    continue
                break
            ## Casting
            elif ins == "cast" and argc == 2 and types == (tuple,str):
                if args[0][0] == "int":
                    self.local_set(args[1],int(self.local_get(args[1])))
                elif args[0][0] == "float":
                    self.local_set(args[1],float(self.local_get(args[1])))
                elif args[0][0] == "string":
                    self.local_set(args[1],str(self.local_get(args[1])))
                else:
                    print(": Invalid cast!") if show_error else None
                    break
            ## Type Checking
            elif ins == "istype" and argc == 3 and types[2] == list and types[0] == str:
                ot, o, c = args
                if ot == "any" or ot == type(o).__name__:
                    if self.run(c,bname=bname,show_error=show_error):
                        break
                del ot, o, c
            elif ins == "isnttype" and argc == 3 and types[2] == list and types[0] == str:
                ot, o, c = args
                if ot != type(o).__name__:
                    if self.run(c,bname=bname,show_error=show_error):
                        break
                del ot, o, c
            elif ins == "isnone" and argc == 2 and types == (str,list):
                ot, c = args
                if ot == "0":
                    if self.run(c,bname=bname,show_error=show_error):
                        break
                del ot, c
            elif ins == "isntnone" and argc == 2 and types == (str,list):
                ot, c = args
                if ot != "0":
                    if self.run(c,bname=bname,show_error=show_error):
                        break
                del ot, c
            ## File IO
            elif ins == "open" and argc == 3 and types == (str,str,str):
                if not os.path.isfile(os.path.join(local_path,args[0])) and args[1] in ("r","rb"):
                    print('Error: Not a file!') if show_error else None
                    break
                self.local_set(join(args[2],"file"),open(os.path.join(local_path,args[0]),args[1]))
                self.local_set(join(args[2],"mode"),args[1])
                self.local_set(join(args[2],"name"),args[2])
                self.local_set(join(args[2],"path"),os.path.join(local_path,args[0]))
            elif ins == "read" and argc == 2 and types == (dict,str):
                if "file" not in args[0] or not isinstance(args[0]["file"],FileObject):
                    print("Error: Invalid object! Must be a file object!") if show_error else None
                    break
                if args[0]["mode"] in ("rb","r"):
                    self.local_set(args[1],args[0]["file"].read())
                else: break
            elif ins == "write" and argc == 2 and types == (dict,str):
                if "file" not in args[0] or not isinstance(args[0]["file"],FileObject):
                    print("Error: Invalid object! Must be a file object!") if show_error else None
                    break
                if args[0]["mode"] in ("wb","w","a"):
                    args[0]["file"].write(args[1])
                else: break
            elif ins == "close" and argc == 1 and types == (dict,):
                if "file" not in args[0] or not isinstance(args[0]["file"],FileObject):
                    print("Error: Invalid object! Must be a file object!") if show_error else None
                    break
                args[0]["file"].close()
                self.local_rem(args[0]["name"])
            elif ins == "delfile" and argc == 1 and types == (dict,):
                if "file" not in args[0] or not isinstance(args[0]["file"],FileObject):
                    print("Error: Invalid object! Must be a file object!") if show_error else None
                    break
                args[0]["file"].close()
                os.remove(args[0]["path"])
                self.local_rem(args[0]["name"])
            ## Conditions
            elif ins == "ifTrue" and argc == 4 and types[-1] == list:
                val0, com, val1, body = args
                vals = types[:3]
                val = (vals[0],vals[2])
                if val0 == val1 and com == "eq":
                    self.run(body,bname=bname)
                elif val0 != val1 and com == "ne":
                    self.run(body,bname=bname)
                elif val0 > val1 and com == "gt" and val in ((int,int),(float,int),(int,float)):
                    self.run(body,bname=bname)
                elif val0 < val1 and com == "lt" and val in ((int,int),(float,int),(int,float)):
                    self.run(body,bname=bname)
                elif val0 >= val1 and com == "ge" and val in ((int,int),(float,int),(int,float)):
                    self.run(body,bname=bname)
                elif val0 <= val1 and com == "le" and val in ((int,int),(float,int),(int,float)):
                    self.run(body,bname=bname)
                else:
                    print('Error: Invalid comparison!') if show_error else None
                    break
                del val0, val1, com, body, vals, val
            ## Enum
            elif ins == "enum" and argc == 2 and types == (str,list):
                for i in args[1]:
                    self.local_set(join(args[0],i),f"{args[0]}.{i}")
            else:
                print("Invalid instruction:",ins) if show_error else None
                print("Line:"," - ".join(map(str,line))) if show_error else None
                break
        else:
            return 0
        print("--===[ Error: In block " + f"`{bname}`".ljust(30," ") + "]===--") if show_error else None
        return 1
@cli.command()
def run(file: str, hasargs: bool=False):
    args = [file]
    if hasargs:
        print('Use Pipes `|` to pipe in args, separate by newline.')
        while True:
            l = input(str(len(args))+": ")
            if not l:
                break
            args.append(l)
    k = inter(os.path.dirname(file),argv=args)
    k.run(open(file).read())
@cli.command()
def info():
    print(f'''CSLang [v{VER}]: Cryptic Scripting Language is a programming language capable of OOP.Its like
mixing Python, Lisp and Lua together and pointing a neutron beam ray at it (our indecies start at zero though).
It has easy syntax and easy to learn. It cant interface with any programming languages (yet).
So sit tight and enjoy writing code in it! Have fun!''')
@cli.command()
def instruction_info(instruction: str):
    docus.find_docu(instruction)
@cli.command()
def repr():
    k = inter("~",argv=sys.argv)
    print(f"CSLang v{VER} - REPR")
    while True:
        kk = input(': ')
        if kk == "end":
            exit()
        else:
            k.run(kk)
if len(sys.argv) == 1:
    repr()
else:
    cli()