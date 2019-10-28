import os,copy,shutil
from time import time
from collections import defaultdict
from contextlib import contextmanager

import numpy as np
import torch

class BaseModel(torch.nn.Module):
    checkpoint_dir = 'checkpoints'

    def __init__(self, checkpoint, init=False, weight_scale=0, avg=.999, pytorch_init=False):
        super().__init__()

        self.cp = os.path.join(self.checkpoint_dir, checkpoint)

        self.stats = dict()
        self._tmp_stats = dict()
        
        self.register_statistic('iter',True,'{:<8}')
        self.iter = 0
        self.stats['iter'][2][self.iter] = self.iter

        self.register_statistic('time',True,'{:<8.2f}')
        self.register_statistic('utime',True,'{:<8.2f}')

        def count_iter(self, in_grad, out_grad):
            self.iter += 1
        self.register_backward_hook(count_iter)

        self.define_graph()
        self.cuda()

        if not pytorch_init:
            for parm in self.parameters():
                if weight_scale == 0: parm.data.fill_(0)
                else: parm.data.normal_(0, weight_scale)

        self.avg = avg
        for module in self.modules():
            for name,parm in module.named_parameters():
                if '.' in name: continue # belongs to a submodule
                # warning: things will break if module contains parameters ending in '_avg'
                module.register_buffer(name + '_avg', parm.clone().detach())

        for name,parm in self.named_parameters():
            self.register_statistic('|{}|'.format(name),False,format_str='{<8.0f}')

        self.count_parameters(verbose=True)

    @contextmanager
    def iterate_averaging(self):
        self.eval()
        # this doesn't play well with batchnorm?
        #orig_parms = copy.deepcopy(list(parm.data for parm in self.parameters()))
        #for name,parm in self.named_parameters():
        #    parm.data.copy_(self.state_dict()[name + '_avg'])
        yield
        #for parm, orig in zip(self.parameters(), orig_parms):
        #    parm.data.copy_(orig)
        self.train()

    def initialize(self):
        if os.path.exists(self.cp):
            shutil.rmtree(self.cp)
            os.makedirs(self.cp)
        else:
            os.makedirs(self.cp)
        self.checkpoint()

    def register_statistic(self,key,display,format_str):
        self.stats[key] = [display,format_str,dict()]

    def checkpoint(self):
        for stat,value in self.stats.items():
            with open(os.path.join(self.cp, stat + '.npy'), 'wb') as f:
                np.save(f,value[2])

        torch.save(self.state_dict(), os.path.join(self.cp,'checkpoint.pt'))

    def restore_checkpoint(self):
        for stat in self.stats:
            with open(os.path.join(self.cp, stat + '.npy'), 'rb') as f:
                self.stats[stat][2] = np.load(f,allow_pickle=True).item()

        self.iter = sorted(self.stats['iter'][2])[-1]
        self.load_state_dict(torch.load(os.path.join(self.cp,'checkpoint.pt')))

    # call this last if inheriting to make final updates
    def update_status(self, train_loader, test_loader, last_time, update_time):
        self._tmp_stats['iter'] = self.iter

        for name,parm in self.named_parameters():
            if parm.requires_grad:
                self._tmp_stats['|{}|'.format(name)] = parm.norm().item()

        self._tmp_stats['time'] = time() - last_time
        self._tmp_stats['utime'] = time() - update_time

        # write everything at once to try to avoid interruption mid-write
        for k,v in self._tmp_stats.items():
            self.stats[k][2][self.iter] = v
        self._tmp_stats = dict()

    def status_header(self):
        return '\t'.join(sorted([key for key,val in self.stats.items() if val[0]]))

    def status(self):
        status_str = ''
        for key,val in sorted(self.stats.items()):
            if val[0]:
                format_str = val[1]
                current_val = val[2][self.iter]
                status_str += format_str.format(current_val)
        return status_str

    def define_graph(self, debug=False):
        raise NotImplementedError
    
    def forward(self, x):
        raise NotImplementedError

    def loss(self, yhat, z):
        raise NotImplementedError

    def sample(self):
        raise NotImplementedError
    
    def average_iterates(self):
        for name,parm in self.named_parameters():
            pavg = self.state_dict()[name + '_avg']
            pavg.mul_(self.avg).add_((1.-self.avg)*parm.data)

    def count_parameters(self, verbose=False):
        count = 0
        for name,parm in self.named_parameters():
            if parm.requires_grad:
                if verbose: print('{} {} ({})'.format(name,parm.shape,np.prod(parm.shape)))
                count += np.prod(parm.shape)

        print('Initialized graph with {} parameters'.format(count))

    def sum_weights(self, group):
        sum_dict = defaultdict(int)
        for stat in self.stats.keys():
            if stat[0] != '|' or stat[-1] != '|': continue
            if('_' in stat): subgroup, name = stat[1:-1].split('_')
            else: subgroup = stat[1:-1]
            if subgroup == group:
                for k in self.stats[stat][2].keys():
                    sum_dict[k] += self.stats[stat][2][k]
        return sum_dict

