import itertools
import more_itertools as mit
import sys


class SysContext:
    def __init__(self, processes=[], groups=[], sessions=[], init_pid=1, syslog=[], logging=True):
        self.processes = processes
        self.groups = groups
        self.sessions = sessions
        self.last_pid = 1
        self.init_pid = init_pid
        self.syslog = syslog
        self.logging = logging
        self.self_proc = None
        self.perror = ""
        self.syscounters = {
            "fork":0,
            "setsid":0,
            "setpgid":0,
            "exit":0
        }

    def get_error(self):
        return self.perror

    def system_start(self):
        init = Process()
        self.processes.append(init)
        return

    def sys_schedule(self, algo = lambda l: list(mit.random_permutation(l))[-1]):
        # In modern Linux kernels, schedule mustn't be called from any user processes, so it is no schedule function in the API
        # default algo: random scheduling
        proc = algo(self.processes)
        self.self_proc = proc
        return proc

    def sys_fork(self, caller_proc):
        proc_pids = set(sorted(set([P.p for P in self.processes])))
        if len(proc_pids) >= 2**16-1:
            self.perror = "PIDs range exceeded"
            return -1
        while self.last_pid in proc_pids:
            self.last_pid=(self.last_pid + 1) % (2**16-1)
        self.processes.append(Process(p=self.last_pid, g=caller_proc.g, s=caller_proc.s, pp=caller_proc.p))
        self.syscounters['fork'] +=1
        return self.last_pid

    def sys_exit(self, caller_proc, exit_code=0):
        if caller_proc in self.processes:
            caller_proc.exit_code = exit_code
            self.processes.remove(caller_proc)

        else:
            self.perror = f"No process with {caller_proc} PID in the processes"
            return -1
            
        for proc in self.processes:
            if proc.pp == caller_proc.p:
                proc.pp = self.init_pid
        self.syscounters['exit'] += 1
        return 0

    def sys_setsid(self, caller_proc):
        if caller_proc.p != caller_proc.s:
            caller_proc.g = caller_proc.s = caller_proc.p
            self.syscounters['setsid'] += 1
            return 0
        else:
            self.perror = f"Process {caller_proc.p} is already session leader"
            return -1

    def sys_setpgid(self, caller_proc, pid, pgid):
        """
        Kerrisk's Linux API Book:
        setpgid() sets the PGID of the process specified by pid to pgid.
        
        If pid is zero, then the process ID of the calling process is
        used.  
        
        If pgid is zero, then the PGID of the process specified by
        pid is made the same as its process ID.  
        
        If setpgid() is used to move a process from one process group to another (as is done by
        some shells when creating pipelines), both process groups must be
        part of the same session (see setsid(2) and credentials(7)).  In
        this case, the pgid specifies an existing process group to be
        joined and the session ID of that group must match the session ID
        of the joining process.
        """
        if pid == 0:
            pid = caller_proc.p
            
        if pgid == 0:
            pgid = pid

        if pid == caller_proc.p and pgid == pid:
            if caller_proc.p != caller_proc.s:
                caller_proc.g = caller_proc.p
                self.syscounters['setpgid'] += 1
                return 0
            else:
                self.perror = f"self-setting: process {pid} is already session leader {caller_proc.s}"
                return -1
 
        proc = [item for item in self.processes if item.p == pid]
        if len(proc) == 0:
            # no such process
            self.perror = f"no such process:{pid}"
            # print(f"DBG: processes {[p.p for p in self.processes]}, pid {pid}")
            return -1

        proc = proc[0]

        if proc.s == proc.p == proc.g:
            # process is a session leader (check it on the new linux kernels--may be redundant?)
            self.perror = f"desired process is the session leader"
            return -1

        pgroup = [item for item in self.processes if item.g == pgid]
        if len(pgroup) == 0:
            # no such pgroup
            self.perror = f"no such group"
            return -1
        
        if pgroup[0].s != proc.s:
            # they lay in different sessions
            self.perror = f"processes are in different sessions"
            return -1

        self.syscounters['setpgid'] += 1
        proc.g = pgid
        return 0


class SysAPI:
    def __init__(self, sc=SysContext(), fromstart=True):
        self.context = sc
        if fromstart:
            self.context.system_start()
        
        self.context.self_proc = self.context.processes[0]

    def get_error(self):
        return self.context.get_error()

    def fork(self):
        retcode = self.context.sys_fork(self.context.self_proc)
        if self.context.logging:
            self.util_commit_log(str(self.context.self_proc.p)+" : fork() : "+"retcode = "+str(retcode))
        return retcode

    def exit(self, exit_code=0):
        retcode = self.context.sys_exit(self.context.self_proc)
        if self.context.logging:
            self.util_commit_log(str(self.context.self_proc.p)+" : exit("+str(exit_code)+") : "+"retcode = "+str(retcode))
        return retcode

    def setsid(self):
        retcode = self.context.sys_setsid(self.context.self_proc)
        if self.context.logging:
            self.util_commit_log(str(self.context.self_proc.p)+" : setsid() : " + "retcode = "+str(retcode))
        return retcode

    def setpgid(self, cred: list):
        pid, pgid = cred[0], cred[1]
        retcode = self.context.sys_setpgid(self.context.self_proc, pid, pgid)
        if self.context.logging:
            self.util_commit_log(str(self.context.self_proc.p)+" : setpgid("+str(pid)+", "+str(pgid)+") : " +
                                 "retcode = "+str(retcode))
        return retcode

    def context_switch(self, sp):
        self.context.self_proc = sp

    def util_enable_log(self):
        self.context.logging = True

    def util_disable_log(self):
        self.context.logging = False

    def util_dump_log(self):
        print("System event log:\n# :PID:\tEvent")
        for i, s in enumerate(self.context.syslog):
            print(i, ":", s)

    def util_save_log(self, fn, success_only=False):
        with open(fn, 'w+') as f:
            for i, s in enumerate(self.context.syslog):
                if success_only==True and "retcode = -1" in s:
                    continue
                f.write(f"{i}: {s}\n")

    def util_clean_log(self):
        self.context.syslog=list()

    def util_commit_log(self, event):
        self.context.syslog.append(event)

    def util_ps(self):
        print("PID\tPGID\tSID\tPPID\n------------------------------")
        query = [str(P.p)+"\t"+str(P.g)+"\t"+str(P.s)+"\t"+str(P.pp) for P in self.context.processes]
        for q in query:
            print(q)
        print("------------------------------")

    def dump_as_dict(self):
        return {P.p: {
            'pid': P.p,
            'pgid': P.g,
            'sid': P.s,
            'ppid': P.pp} for P in self.context.processes
        }
        
    def extra_util_get_session_processes(self, s):
        return [P for P in self.context.processes if P.s == s]

    def extra_util_get_pgroup_processes(self, g):
        return [P for P in self.context.processes if P.g == g]

    def extra_return_synced_ps(self, verbose=False):
        query = [{
            'p': {'value': P.p,'sync': False},
            'g': {'value': P.g,'sync': False},
            's': {'value': P.s,'sync': False},
            'pp': {'value': P.pp,'sync': False},
        } for P in self.context.processes]
        if verbose:
            print(query)
        plist = [P.p for P in self.context.processes]
        return query, plist

    def extra_make_upload_from_synced(self, query, save_previous=False):
        if not save_previous:
            self.context.processes = []
        for q in query:
            item = q
           
            P = Process(p=q['p']['value'],g=q['g']['value'],s=q['s']['value'],pp=q['pp']['value'])
            self.context.processes.append(P)

        
class Process:
    def __init__(self, p=1, g=1, s=1, pp=0):
        self.p = p
        self.g = g
        self.s = s
        self.pp = pp
        self.exit_code = 0

    
if __name__ == '__main__':
    API = SysAPI()
    API.fork()
    API.context_switch(API.context.processes[1])
    API.fork()
    API.util_ps()
    API.setpgid([0, 2])
    API.util_ps()
    API.setsid()
    API.util_ps()
    API.exit()
    API.util_ps()
    API.util_dump_log()
    print(API.dump_as_dict())
    sys.exit(0)
    # scheduling example:
    while (True):
        print(API.context.sys_schedule().p)
        
