import os,copy
from time import time
from contextlib import contextmanager

import numpy as np
import torch

from .dataset import worker_config

def optimize(model, train_set, test_set, learning_rate=0.01, momentum=.95, batch_size=1000, epochs=40, workers=4, update_rate=1000, l2=0, alg='SGD'):
    worker_config['num_workers'] = workers

    train_loader = torch.utils.data.DataLoader(dataset=train_set,batch_size=batch_size,shuffle=True,**worker_config)

    prng = np.random.RandomState(999)
    test_loader = torch.utils.data.DataLoader(dataset=test_set,batch_size=batch_size,**worker_config)
    train_loader = torch.utils.data.DataLoader(dataset=train_set,batch_size=batch_size,**worker_config)

    print('Initiating optimizer, {} iterations/epoch.'.format(len(train_loader)))
    model.restore_checkpoint()
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
                    with model.iterate_averaging():
                        model.update_status(train_loader, test_loader, t, time())
                    model.checkpoint()
                    print(model.status())
                    t = time()

                optimizer.zero_grad()
                x,y = model.prepare_data(x,y)
                loss = model.loss(model(x,y),y)
                loss.backward()
                optimizer.step()
                model.average_iterates()

    except KeyboardInterrupt:
        print('Graceful Exit')
    else:
        print('Finished')

