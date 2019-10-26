Workspace for the July 27 civic hackathon

#Setup:
Create a folder 'data' on the same level as this readme. Download the ML test data from AWS (details in `access.md` in orcadata).

#Instructions for `linear16384.ipynb`
## Dependencies
Python libraries: pytorch, interval_tree, anaconda
Jupyter notebooks (should come with anaconda), in order to view the notebook

## Troubleshooting
On error `cannot import name 'signature' from 'sklearn.utils.fixes'`: Open `media.py` and comment out the line `from sklearn.utils.fixes import signature`. You should also replace the body of `plot_pr_curve` with something like `print("Not plotting")`. You won't be able to plot PR curves, but the model will still train.
