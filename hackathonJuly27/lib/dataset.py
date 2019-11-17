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
    def __init__(self, root, train=True, normalize=True, window=16384, translate=False, pitch_shift=0, jitter=0., stride=512, split=25*60, collapse_labels=True):
        self.normalize = normalize
        self.window = window
        self.pitch_shift = pitch_shift
        self.jitter = jitter
        self.translate = translate
        self.stride = stride
        self.m = len(['call','buzz','whistle'])
        self.collapse_labels = collapse_labels

        self.root = os.path.expanduser(root)

        fs,data = wavfile.read(os.path.join(root,'OS_7_05_2019_08_24_00_.wav'))
        labels = IntervalTree()
        with open(os.path.join(root,'OS_7_05_2019_08_24_00_labels.txt')) as f:
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
        if self.pitch_shift > 0:
            shift = np.random.randint(-self.pitch_shift,self.pitch_shift)

        jitter = 0.
        if self.jitter > 0:
            jitter_amount = np.random.uniform(-self.jitter,self.jitter)

        s = i*self.stride
        if self.translate: s += np.random.randint(self.stride)
        return self.access(s,shift,jitter)

    def __len__(self):
        return len(self.data)//self.stride

class WhoisDataset(data.Dataset):
    def __init__(self, root, train=True, normalize=True, window=16384, translate=False, pitch_shift=0, jitter=0., stride=512):
        self.normalize = normalize
        self.window = window
        self.pitch_shift = pitch_shift
        self.jitter = jitter
        self.translate = translate
        self.stride = stride

        self.root = os.path.join(os.path.expanduser(root),'whois/train_data_09222019/')
        if train: labelfile = os.path.join(self.root,'train.tsv')
        else: labelfile = os.path.join(self.root,'dev.tsv')

        fs = 44100.
        self.size = 0
        self.data = dict()
        self.labels = dict()
        self._base_idx = dict()
        self._cumsize = dict()
        with open(labelfile) as f:
            for i,(wav,start,dur,loc,date,master) in enumerate(csv.reader(f, delimiter='\t')):
                if i == 0: continue
                if wav not in self.data.keys():
                    xfs, x = wavfile.read(os.path.join(self.root,'wav',wav))
                    xp = np.arange((fs/xfs)*len(x),dtype=np.float32)
                    x = np.interp((xfs/fs)*xp,np.arange(len(x),dtype=np.float32),x).astype(np.float32)
                    self.data[wav] = x
                    self.labels[wav] = IntervalTree()
                    self._base_idx[wav] = self.size
                    self._cumsize[self.size] = wav
                    self.size += len(x) // self.stride
        
                if float(dur) < 0.1: continue
                self.labels[wav][int(float(start)*fs):int((float(start)+float(dur))*fs)] = 1

        self._sorted_base = sorted(self._cumsize.keys())
        print('Loaded dataset with {} datapoints'.format(self.size))

    def location_to_index(self, wav, s):
        return self._base_idx[wav] + s//self.stride

    def index_to_location(self, i):
        base = self._sorted_base[np.searchsorted(self._sorted_base,i,'right')-1]
        wav = self._cumsize[base]
        s = self.stride*(i - base)
        return wav,s

    def access(self,wav,s,shift=0,jitter=0):
        scale = 2.**((shift+jitter)/12.)
        scaled_window = int(scale*self.window)

        start = max(0,s-scaled_window//2)
        end = min(s+scaled_window//2,len(self.data[wav]))
        x = self.data[wav][start:end]
        x = np.pad(x,(start - (s - scaled_window//2),(s + scaled_window//2) - end),'constant')

        if self.normalize: x /= np.linalg.norm(x) + 10e-8

        xp = np.arange(self.window,dtype=np.float32)
        x = np.interp(scale*xp,np.arange(len(x),dtype=np.float32),x).astype(np.float32)

        y = np.zeros(1,dtype=np.float32)
        y[0] = 1 if len(self.labels[wav][s]) > 0 else 0

        return x,y

    def __getitem__(self, i):
        if i >= len(self): raise IndexError

        shift = 0
        if self.pitch_shift > 0:
            shift = np.random.randint(-self.pitch_shift,self.pitch_shift)

        jitter = 0.
        if self.jitter > 0:
            jitter_amount = np.random.uniform(-self.jitter,self.jitter)

        wav, s = self.index_to_location(i)
        if self.translate: s += np.random.randint(self.stride)
        return self.access(wav,s,shift,jitter)

    def __len__(self):
        return self.size
