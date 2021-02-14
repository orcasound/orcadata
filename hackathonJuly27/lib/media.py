import matplotlib
import matplotlib.pyplot as plt

from sklearn.metrics import precision_recall_curve
from funcsigs import signature

def plot_pr_curve(y,yhat):
    precision,recall,_ = precision_recall_curve(y.ravel(), yhat.ravel())

    step_kwargs = ({'step': 'post'}
                   if 'step' in signature(plt.fill_between).parameters
                   else {})
    plt.step(recall, precision, color='b', alpha=0.2, where='post')
    plt.fill_between(recall, precision, alpha=0.2, color='b', **step_kwargs)
    plt.grid(color='b', linestyle='--', linewidth=0.5, alpha=0.3)

class PlotFormatter():
    def __init__(self,burnin=1):
        self.plots = []
        self.plot_count = 0
        self.burnin = burnin

    def plot(self,title,vals,color,share=False):
        self.plots.append((title,vals,color,share))
        if not share: self.plot_count += 1

    def show(self,burnin=None):
        if burnin == None: burnin = self.burnin
        rows = self.plot_count//2 + self.plot_count%2
        fig, axes = plt.subplots(rows,2)
        fig.set_figwidth(12)
        fig.set_figheight(5*rows)

        plot_idx = -1
        for i in range(len(self.plots)):
            title, vals, color, share = self.plots[i]
            if not share: plot_idx += 1
            ax = axes[plot_idx//2,plot_idx%2]
            ax.set_title(title)
            ax.grid(color='b', linestyle='--', linewidth=0.5, alpha=0.3)
            x = [k for k in sorted(vals.keys()) if k >= burnin]
            y = [vals[k] for k in x]
            ax.plot(x,y,color=color)
