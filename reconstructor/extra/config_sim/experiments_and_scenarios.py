import os
import sys

import numpy as np
import pprint
import random
import math
import networkx as nx
from datetime import datetime
from simulator import *
from interpret import *
import json
import networkx.algorithms.graph_hashing as graph_hashing


# Print iterations progress
def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

def load_strace(inp):
    syscalls = []
    for line in [d for d in input]:
        if any(line.startsWith(item) for item in ['fork', 'clone', 'vfork', 'setsid', 'setpgid', 'exit']):
            syscalls.append(line)

    for line in syscalls:
        pass


def edge_check(T, src, dst, label, method="appprox"):
    if method=="accurate":
        for e in T.get_edges():
            if e.get_source() == src and e.get_destination() == dst and e.get_attributes['label'] == label:
                return True
    
    return False


def pydot_tree_to_structured_full_repr(T):
    nodes = T.get_nodes()

    for n in nodes:
        #p = n.get_attributes("p")
        g = n.get_attributes()["g"]
        s = n.get_attributes()["s"]
        pp = n.get_attributes()["pp"]
        lg = [P for P in nodes if P.get_attributes()["g"]==P.get_attributes()["p"]==g]
        if len(lg) > 0 and not edge_check(T,lg[0], n, label="group"): # process-group-leader is in pstree
           T.add_edge(pydot.Edge(lg[0], n, label="group",color="lightcoral"))
        elif len([P for P in nodes if P.get_attributes()["p"]==g])>1: # process-group-leader is in not pstree, but there is a process with such pid
            lg = ([P for P in nodes if P.get_attributes()["p"]==g])[0]
            imn = pydot.Node(s=s,p=lg[0],g=g,pp=-1, label=str(s)+" "+str(s)+" "+str(s)+" "+str(lg[0].get_attrubutes()["pp"]))
            T.add_edge(pydot.Edge(imn, lg[0], label="g_leader_deset"))
            T.add_edge(pydot.Edge(lg[0], n, label="g_leader_imn"))

        else: # no such processes
            imn = pydot.Node(s=s,p=g,g=g,pp=-1, label=str(g)+" "+str(g)+" "+str(s)+" "+str(-1))
            
        ls = [P for P in nodes if P.get_attributes()["s"] == P.get_attributes()["p"] == s]
        if (len(ls)>0): # process-session-leader is in pstree
            if not edge_check(T,ls[0], n, label="session"):
                T.add_edge(pydot.Edge(ls[0], n, label="session",color="lightblue"))
        else: # no such processes
            imn = pydot.Node(s=s,p=s,g=s,pp=-1, label=str(s)+" "+str(s)+" "+str(s)+" "+str(-1))
            if not edge_check(T,imn, n, label="s_leader_imn"):
                T.add_edge(pydot.Edge(imn, n, label="s_leader_imn"))
    return T


def pstree_to_structured_full_repr(pslist=[], mode='current_host_ps', path=None):
    API = SysAPI()
    #interpret(API)
    if mode == 'current_host_ps':
        checkpoint_full_tree_reload(API, get_current_host_ps())
    elif mode == 'from_fs':
        checkpoint_full_tree_reload(API, load_ps(path, " "))
    else:
        return None

    T = make_pstree(API.context.processes)
    nodes = T.get_nodes()
    for n in nodes:
        #p = n.get_attributes("p")
        g = n.get_attributes()["g"]
        s = n.get_attributes()["s"]
        pp = n.get_attributes()["pp"]
        lg = [P for P in nodes if P.get_attributes()["g"] == P.get_attributes()["p"] == g]
        if len(lg) > 0: # process-group-leader is in pstree
           T.add_edge(pydot.Edge(lg[0], n, label="group",color="lightcoral"))
        elif len([P for P in nodes if P.get_attributes()["p"] == g]) > 1:  # process-group-leader is in not pstree, but there is a process with such pid
            lg = ([P for P in nodes if P.get_attributes()["p"] == g])[0]
            imn = pydot.Node(s=s, p=lg[0], g=g, pp=-1,
                             label=str(s)+" "+str(s)+" "+str(s)+" "+str(lg[0].get_attrubutes()["pp"]))
            T.add_edge(imn, lg[0], label="g_leader_deset")
            T.add_edge(lg[0], n, label="g_leader_imn")

        else: # no such processes
            imn = pydot.Node(s=s,p=g,g=g,pp=-1, label=str(g)+" "+str(g)+" "+str(s)+" "+str(-1))
            T.add_edge(imn, n, label="g_leader_imn")
            
        ls = [P for P in nodes if P.get_attributes()["s"]==P.get_attributes()["p"]==s]
        if len(ls) > 0:  # process-session-leader is in pstree
            T.add_edge(pydot.Edge(ls[0], n, label="session",color="gold"))
        else: # no such processes
            imn = pydot.Node(s=s,p=s,g=s,pp=-1, label=str(s)+" "+str(s)+" "+str(s)+" "+str(-1))
            T.add_edge(imn, n, label="s_leader_imn")
        
    return T


def write_ps_to_file(API, fn):
    f = open(fn, 'w')
    f.write("PID\tPGID\tSID\tPPID\n")
    query = [str(P.p)+"\t"+str(P.g)+"\t"+str(P.s)+"\t"+str(P.pp)+"\n" for P in API.context.processes]
    for q in query:
       f.write(q)
    f.close()


def write_json_to_file(API, fn):
    query = {P.p: {'pid': P.p, 'pgid': P.g,'sid': P.s, 'ppid': P.pp} for P in API.context.processes}
    with open(fn, 'w') as fp:
        json.dump(query, fp)


def random_syscalls(API, sc_, steps,
                    verbose=False, exp_name="synthetic", loc_fn="0", preset="N/A"):
    i = 0
    sc_list = sc_[0]
    weights = sc_[1]
    while i < steps:
        if verbose is False:
            printProgressBar(i ,steps, prefix=f"{exp_name}: PTree no. {loc_fn} generation")

        self_ = API.context.sys_schedule()
        syscall = random.choices(sc_list, weights=weights)[0]
        if syscall == 'setpgid':
            '''Trying to set for process {first}: group {second} by the {self_.p}'''
            if preset is not None:
                if "simple" in preset:
                    first = 0
                    second = random.choice([P.g for P in API.extra_util_get_session_processes(self_.s)])
                elif "accurate" in preset:
                    first_choice = random.choice([P.p for P in API.extra_util_get_session_processes(self_.s)])
                    first = random.choice([first_choice, 0])
                    second_choice = random.choice([P.g for P in API.extra_util_get_session_processes(self_.s)])
                    second = random.choice([second_choice, first])
                    if first == second == self_.p and self_.g == self_.p:
                        continue
                else:
                    first = random.choice([P.p for P in API.context.processes])
                    second = random.choice([P.g for P in API.context.processes])
            args_list = [first, second]
        else:
            if syscall == "exit":
                if self_.p == 1:
                    if verbose:
                        print("Force omit for init to exit")
                    continue
            args_list = [0]

        ret = perform_syscall(API, syscall, args_list)

        if ret is None or ret < 0:
            if verbose is True:
                print(bcolors.WARNING+"[Warning]: during interpretation of:"+bcolors. ENDC,
                      str(i),
                      "command:", syscall, args_list, "; PID", str(self_.p), ":", ret)
                print(API.get_error())
        else:
            i = sum([API.context.syscounters[c] for c in sc_list])
    if verbose:
        API.util_ps()
        API.util_dump_log()
        print("Syscounters:", API.context.syscounters)

    write_ps_to_file(API, exp_name + os.sep+"ps"+loc_fn + ".csv")
    API.util_save_log(exp_name + os.sep + "ps" + loc_fn + "_events.txt", success_only=True)
    write_json_to_file(API, exp_name + os.sep+"ps"+loc_fn+".json")


def rand_sysc_test(loops=1, steps=100):
    for i in range(loops):
        API = SysAPI()
        SC = [['fork','setsid','setpgid','exit'], [0.25, 0.25, 0.25, 0.25]]
        random_syscalls(API=API, sc_=SC, steps=steps)
        del API

    
def isomorphism_check(G1, G2, checker="WL_node", iterations=3):
    if checker == "DEFAULT":
        res = nx.is_isomorphic(G1, G2)

    elif checker.startswith( "WL" ):
        attrs= nx.get_edge_attributes(G1, 'label')
        attr_list = [v for _,v in attrs.items()]
        nx.set_edge_attributes(G1, attr_list, 'label')
        attrs= nx.get_edge_attributes(G2, 'label')
        attr_list = [v for _, v in attrs.items()]
        nx.set_edge_attributes(G2, attr_list, 'label')

        r1 = graph_hashing.weisfeiler_lehman_graph_hash(G1, node_attr='label', iterations=iterations) if checker.endswith("node") \
                        else graph_hashing.weisfeiler_lehman_graph_hash(G1, iterations=iterations)
        r2 = graph_hashing.weisfeiler_lehman_graph_hash(G2, node_attr='label', iterations=iterations) if checker.endswith("node") \
                        else graph_hashing.weisfeiler_lehman_graph_hash(G2, iterations=iterations)
        res = math.fabs(int(r1,16) - int(r2,16))
        
    else:
        #add your custom procedure
        res = False
        if not res:
            pass # set WL metric
            return res, 0
    return res, 0


def update_sync_query(query, old, new):
    new_dict = {k: v for k, v in zip(old, new)}
    for item in query:  
        for k,v in item.items():
            if v['value'] in new_dict.keys() and v['sync'] == False:
                v['value'] = new_dict[v['value']]
                v['sync'] = True
        
    return query


def permute_ps(API, allow_shifts=False, verbose=True, prefix="0"):
    query, old = API.extra_return_synced_ps(verbose=False)
    new = list(np.random.permutation(old[1:]))
    new = old[:1] + new

    if allow_shifts == True:
        #print("Before shifting:", new)
        for i,item in enumerate(new[1:]):
            shift = random.randrange(0, 2**16-1, 1)
            if (item + shift)%2**16-1 not in new[1:]:
                new[i+1] = (item + shift)%2**16-1

        #print("After shifting:", new)

    query = update_sync_query(query, old, new)
    API.extra_make_upload_from_synced(query, save_previous=False)
    if verbose:
        #API.util_ps()
        T = make_pstree(API.context.processes)
        render_pstree(T, prefix+".png")
    return API
    
    
def make_permutations(API, iters=100, shift=False, verbose=False, exp_name="plots"):
    pydot_obj_trees_list = []
    for i in range(iters):
        if verbose:
            #API.util_ps()
            T = make_pstree(API.context.processes)
            pydot_obj_trees_list.append(T)
            if not os.path.exists(exp_name):
                os.makedirs(exp_name)
            render_pstree(T, exp_name + os.sep + (str)(i) + "_.png")
            T.write_raw('output_raw.dot')

        printProgressBar(i + 1, iters, prefix = 'Progress:', suffix = 'Complete', length = 100)
        permute_ps(API, allow_shifts=shift)
    return pydot_obj_trees_list


def isom_check(infile=None, iterations=3):
    exp_name = "plots"
    if len(sys.argv) >= 2 and (sys.argv[1].startswith("-isom") or sys.argv[1].startswith("-augm_isom")):
        API = SysAPI()
        if not infile:
            checkpoint_full_tree_reload(API, get_current_host_ps())
        else:
            checkpoint_full_tree_reload(API, load_ps_from_fs(fn=infile,delimiter="\t"))
        if sys.argv[1].endswith("shift_val"):
            shift = True
        else:
            shift = False
        bank = make_permutations(API,iters=20, shift=shift, verbose=True)
        initial = bank[0]
        G1 = pydot_tree_to_structured_full_repr(initial)

        print("----------------------------------------------------------------------------------------------------------------\nHashes calculation & comparing...")
        results = []
        for i, t in enumerate(bank[1:]):
            printProgressBar(i + 1, len(bank)-1, prefix = 'Progress:', suffix = 'Complete', length = 100)
            G2 = t
            checker = "WL_node"
            if sys.argv[1].startswith("-augm_isom"):
                G2 = pydot_tree_to_structured_full_repr(t)
                try:
                    G1.write_png(exp_name + os.sep + "temp" + str(i)+"orig.png")
                    G2.write_png(exp_name + os.sep + "temp" + str(i)+"t.png")
                except:
                    pass
                checker = "WL_edge"
            results.append((isomorphism_check(nx.nx_pydot.from_pydot(G1), nx.nx_pydot.from_pydot(G2),
             checker=checker, iterations=iterations), initial, t))

        lst = [r[0][0] for r in results]
        nze = [idx for idx, val in enumerate(lst) if val != 0]
        print("Results:")
        print(results)
        print(str(len(nze)/len(lst)*100)+" % is strictly non-isomorfic", ": "+str(nze) + " -- indexes" if len(nze)>0 else "")
        print("----------------------------------------------------------------------------------------------------------------")
        print("Results:\n")
        pprint.pprint(
        [(i,r[0]) for i,r in enumerate(results)]
        )
    else:
        psl = get_current_host_ps()
        Tstar = pstree_to_structured_full_repr(pslist=psl)
        render_pstree(Tstar, "1.png")


def main():
    exp_name = "dataset_context" # + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    gen_syscalls_list = ['fork', 'setsid', 'setpgid', 'exit']
    weights = [0.5, 0.1, 0.3, 0.1]
    steps = 12000
    if len(sys.argv) >= 2 and (sys.argv[1].startswith("-isom") or sys.argv[1].startswith("-augm_isom")):
        isom_check(infile="context/ps5133.ps", iterations=0)

    elif len(sys.argv) > 2 and (sys.argv[1].startswith("-gen")):
        API = SysAPI()
        if len(sys.argv) > 3:
            steps = int(sys.argv[3])
            exp_name += os.sep + sys.argv[3]
        if not os.path.exists(exp_name):
            os.makedirs(exp_name, exist_ok=True)

        random_syscalls(API, steps=steps,
                        sc_=[gen_syscalls_list, weights],
                        verbose=False,
                        exp_name=exp_name,
                        loc_fn=sys.argv[2],
                        preset="accurate")

    elif len(sys.argv) >= 2 and (sys.argv[1].startswith("-vis")):
        from os import walk
        f = []
        for (dirpath, dirnames, filenames) in walk("." + os.sep + exp_name):
            f.extend(filenames)
            break
        for i, fn in enumerate(f):
            data = load_ps_from_fs("./" + exp_name + os.sep + fn, delimiter="\t")
            API = SysAPI()
            checkpoint_full_tree_reload(API, data)
            G=make_pstree(pslist=API.context.processes)
            if len(sys.argv) >= 3 and sys.argv[2] == 'json':
                j = API.dump_as_dict()
                json.dump(j, "./" + exp_name + os.sep + fn+'.json')
            render_pstree(G, "output" + os.sep + str(i)+".png")

    elif len(sys.argv) >= 2 and (sys.argv[1].startswith("-wl_par_algo_test")):
         isom_check(infile=None)


if __name__ == '__main__':
    main()