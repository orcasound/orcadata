import os,copy
from time import time
from contextlib import contextmanager

import numpy as np
import torch

from .dataset import worker_config

def optimize(model, train_set, test_set, learning_rate=0.01, momentum=.95, batch_size=1000, epochs=40, workers=4, update_rate=1000, l2=0, alg='SGD', sample_size=20000):
    worker_config['num_workers'] = workers

    train_loader = torch.utils.data.DataLoader(dataset=train_set,batch_size=batch_size,shuffle=True,**worker_config)
    test_loader = torch.utils.data.DataLoader(dataset=test_set,batch_size=batch_size,**worker_config)

    prng = np.random.RandomState(999)
    train_sampler = torch.utils.data.sampler.SubsetRandomSampler(prng.choice(range(len(train_set)),min(sample_size,len(train_set)),replace=False))
    train_sample_loader = torch.utils.data.DataLoader(dataset=train_set,batch_size=batch_size,sampler=train_sampler,**worker_config)

    print('Initiating optimizer, {} iterations/epoch.'.format(len(train_loader)))
    print(model.status_header())

    if alg == 'SGD':
        optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate, momentum=momentum, weight_decay=l2)
    elif alg == 'Adam':
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=l2)
    else:
        raise ValueError('Unrecognized optimizer request')

    try:
        t = time()
        for epoch in range(epochs):
            for i, (x,y) in enumerate(train_loader):
                if i % update_rate == 0:
                    model.update_status(train_sample_loader, test_loader, t, time())
                    model.checkpoint()
                    print(model.status())
                    t = time()

                model.train()
                optimizer.zero_grad()
                x,y = model.prepare_data(x,y)
                loss = model.loss(model(x,y),y)
                loss.backward()
                optimizer.step()
                model.average_iterates()
                model.eval()

    except KeyboardInterrupt:
        print('Graceful Exit')
    else:
        print('Finished')

