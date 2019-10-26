import os,signal,os.path,mmap,errno,csv,pickle
from time import time

import numpy as np
from scipy.io import wavfile
import torch.utils.data as data
from intervaltree import IntervalTree

sz_float = 4 # size of a float

def _worker_init(args):
    signal.signal(signal.SIGINT, signal.SIG_IGN) # ignore signals so parent can handle them
    np.random.seed(os.getpid() ^ int(time())) # approximately random seed for workers

# default configuration for dataloader workers
worker_config = {'num_workers': 4, 'pin_memory': True, 'worker_init_fn': _worker_init}

class OrcaDataset(data.Dataset):
    def __init__(self, root, train=True, normalize=True, window=16384, pitch_shift=0, jitter=0., stride=512, split=25*60, collapse_labels=True):
        self.normalize = normalize
        self.window = window
        self.pitch_shift = pitch_shift
        self.jitter = jitter
        self.stride = stride
        self.m = len(['call','buzz','whistle'])
        self.collapse_labels = collapse_labels

        self.root = os.path.expanduser(root)

        fs,data = wavfile.read('data/OS_7_05_2019_08_24_00_.wav')
        labels = IntervalTree()
        with open('data/OS_7_05_2019_08_24_00_labels.txt') as f:
            for start,end,label in csv.reader(f, delimiter='\t'):
                if start == '\\': continue
                label = label.strip().replace(' ', '')
                if 'call' in label or 'cll' in label or 'cal' in label:
                    labels[int(float(start)*fs):int(float(end)*fs)] = 0
                elif 'buzz' in label:
                    labels[int(float(start)*fs):int(float(end)*fs)] = 1
                elif 'whistle' in label:
                    labels[int(float(start)*fs):int(float(end)*fs)] = 2
                else:
                    continue

        if train:
            self.data = data[:split*fs].astype(np.float32).sum(1) # float mono
            self.labels = IntervalTree(labels[:split*fs])
        else: # test
            self.data = data[split*fs:].astype(np.float32).sum(1) # float mono
            self.labels = IntervalTree()
            for start,end,label in labels[split*fs:]:
                self.labels[start-split*fs:end-split*fs] = label

        print('Loaded dataset with {} datapoints'.format(len(self.data)//stride))

    def access(self,s,shift=0,jitter=0):
        scale = 2.**((shift+jitter)/12.)
        scaled_window = int(scale*self.window)

        start = max(0,s-scaled_window//2)
        end = min(s+scaled_window//2,len(self.data))
        x = self.data[start:end]
        x = np.pad(x,(start - (s - scaled_window//2),(s + scaled_window//2) - end),'constant')

        if self.normalize: x /= np.linalg.norm(x) + 10e-8

        xp = np.arange(self.window,dtype=np.float32)
        x = np.interp(scale*xp,np.arange(len(x),dtype=np.float32),x).astype(np.float32)

        y = np.zeros([self.m],dtype=np.float32)
        for label in self.labels[s]: 
            y[label.data] = 1
        if self.collapse_labels: y = np.max(y,keepdims=True)

        return x,y

    def __getitem__(self, i):
        if i >= len(self): raise IndexError

        shift = 0
        if self.pitch_shift> 0:
            shift = np.random.randint(-self.pitch_shift,self.pitch_shift)

        jitter = 0.
        if self.jitter > 0:
            jitter_amount = np.random.uniform(-self.jitter,self.jitter)

        s = i*self.stride
        #s += np.random.randint(self.stride)
        return self.access(s,shift,jitter)

    def __len__(self):
        return len(self.data)//self.stride

