import numpy as np

import torch
import torch.nn.functional as F

from sklearn.metrics import average_precision_score
from sklearn.metrics import accuracy_score

from .model import BaseModel

class AcousticModel(BaseModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        #self.register_statistic('acc_tr',True,'{:<8.2f}')
        #self.register_statistic('acc_ts',True,'{:<8.2f}')
        self.register_statistic('avp_ts',True,'{:<8.2f}')
        self.register_statistic('avp_tr',True,'{:<8.2f}')
        self.register_statistic('loss_ts',True,'{:<8.3f}')
        self.register_statistic('loss_tr',True,'{:<8.3f}')

    def loss(self, yhat, y):
        return F.mse_loss(yhat, y)/2.

    def prepare_data(self, x, y):
        # ship everything over to the gpu
        return x.cuda(),y.cuda()

    def compute_stats(self, loader):
        yhat,y = self.predict_all(loader)
        loss = ((yhat-y)**2).mean()/2.
        avp = average_precision_score(y.ravel(),yhat.ravel(),average=None)
        return loss, avp

    def predict_all(self, loader):
        loss = 0
        batch = loader.batch_size
        yhat_all = np.empty([len(loader)*batch,self.m])
        y_all = np.empty([len(loader)*batch,self.m])

        with self.iterate_averaging():
            for i, (x,y) in enumerate(loader):
                x,y = self.prepare_data(x,y)
                yhat = self(x,y)
                yhat_all[i*batch:i*batch+x.shape[0]] = yhat.detach().cpu().numpy()
                y_all[i*batch:i*batch+x.shape[0]] = y.detach().cpu().numpy()

            # remove unusued allocated prediction space if there's an incomplete final batch
            if batch - x.shape[0] > 0:
                yhat_all = yhat_all[:x.shape[0]-batch]
                y_all = y_all[:x.shape[0]-batch]

        return yhat_all,y_all

    def update_status(self, train_loader, test_loader, last_time, update_time):
        loss, avp = self.compute_stats(test_loader)
        self._tmp_stats['loss_ts'] = loss
        self._tmp_stats['avp_ts'] = 100*avp

        loss, avp = self.compute_stats(train_loader)
        self._tmp_stats['loss_tr'] = loss
        self._tmp_stats['avp_tr'] = 100*avp

        super().update_status(train_loader, test_loader, last_time, update_time)

    def create_filters(self,d,k,low=50,high=6000):
        x = np.linspace(0, 2*np.pi, d, endpoint=False)
        wsin = np.empty((k,1,d), dtype=np.float32)
        wcos = np.empty((k,1,d), dtype=np.float32)
        start_freq = low
        end_freq = high
        num_cycles = start_freq*d/44000.
        scaling_ind = np.log(end_freq/start_freq)/k
        window_mask = 1.0-1.0*np.cos(x)
        for ind in range(k):
            wsin[ind,0,:] = window_mask*np.sin(np.exp(ind*scaling_ind)*num_cycles*x)
            wcos[ind,0,:] = window_mask*np.cos(np.exp(ind*scaling_ind)*num_cycles*x)

        wsin = torch.from_numpy(wsin).cuda()
        wcos = torch.from_numpy(wcos).cuda()
        
        return wsin,wcos
