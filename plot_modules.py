
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import sampling_modules as sm
mpl.use('Agg')
import pandas as pd
import seaborn as sns
import os
import sys
import tensorflow as tf
def init_violin_plots(self,loops_2_show):
    'initilize the violin plots'
    nb_violinplots = len(loops_2_show)
    for k in np.arange(nb_violinplots):
        self.vp.append(plt.subplots(1, 1, figsize=[5, 3], dpi=300))
    return self.vp


def plot_violin(self, i, j, seq, steps_2_show, loops_2_show):
    # i is the step number
    # j is the Loop number
    # TODO: Should show the min yield as a red line - not the median
    idx_loop = np.argmax(loops_2_show == j)
    idx_step = np.argmax(steps_2_show == i)
    dev = seq['Developability'].to_numpy()  # yield
    violin_parts = self.vp[idx_loop][1].violinplot([dev], positions=[idx_step], showmedians=False,
                                                   showextrema=False, points=100,
                                                   widths=.9)
    for pc in violin_parts['bodies']:
        pc.set_color('k')


def close_violin(self, j, steps_2_show, loops_2_show, Nb_steps, Nb_loops, y_lim=None):
    'close a violin plot and save it as a png file'
    if y_lim is None:
        y_lim = [-1, 1.5]
    v = self.vp[np.argmax(loops_2_show == j)]
    str_steps_2_show = []
    for i in steps_2_show:
        if i == 0:
            str_steps_2_show.append('Init')
        else:
            str_steps_2_show.append('step:%i,percent:%0.2f' % (i,sum(self.percent_pos[j])/Nb_steps))
    fig = v[0]
    ax = v[1]
    ax.set_xticks(np.arange(len(steps_2_show)))
    ax.set_ylim(y_lim)
    ax.set_xticklabels(str_steps_2_show)
    ax.set_ylabel('Yield', fontsize=6)
    ax.tick_params(axis='both', which='major', labelsize=6)
    ax.set_title('Loop %i of %i' % (j + 1, Nb_loops))
    ax.axhline(self.min_yield[j]).set_color('r')
    fig.tight_layout()
    print('saving'+make_file_name(dir_name=self.dir_name,file_description='loop_%i'%(j+1),fileformat='png'))
    fig.savefig(make_file_name(dir_name=self.dir_name,file_description='loop_%i'%(j+1),fileformat='png'))
    plt.close(fig)



def make_min_yield_plot(dir_name, N_loops, min_yield_lst):
    'this makes the min yield plot'
    plt.plot(np.arange(N_loops + 1).tolist(), min_yield_lst)
    plt.title('min yield vs. nb of loops')
    plt.ylabel('min yield')
    plt.xlabel('nb of loops')
    plt.savefig(make_file_name(dir_name=dir_name,file_description='min_yield',fileformat='png'))
    plt.close()

def make_percent_positive_plot(dir_name, N_loops, N_steps,percent_pos):
    'makes the percent positive plot '
    pp = []
    for i in np.arange(N_loops):
        pp.append(sum(percent_pos[i])/ N_steps) # Right now percent postive is just the average ...
    plt.plot(np.arange(N_loops).tolist(), pp)
    plt.title('percent accepted vs. for each loop')
    plt.ylabel('percent accepted')
    plt.xlabel('# of loops')
    plt.savefig(make_file_name(dir_name=dir_name,file_description='percent_pos',fileformat='png'))
    plt.close()


def plot_hist(dir_name, i, j, seq,bins=50):
    # future version
    print('Plotting histogram Step:%i,Loop%i' % (i, j))
    dev=seq['Developability'].to_numpy()
    plt.hist(dev, bins=bins)
    plt.title('Step: %i Loop: %i threshold yield: %0.2f'
              % (i, j, np.min(dev)))
    plt.ylabel('frequency')
    plt.xlabel('yield')
    plt.savefig(make_file_name(dir_name=dir_name,file_description='hist_loop_%i_step%i'%(j,i),fileformat='png'))
    plt.close()


def make_file_name(dir_name,file_description,fileformat=None):
    if fileformat is None:
        return './sampling_data/' + dir_name+'/'+ file_description
    else:
        return './sampling_data/' + dir_name+'/'+ file_description +'.'+fileformat



def make_heat_map(df,dir_name,loop_nb):
    ord=sm.convert2numpy(df=df,field='Ordinal')
    nb_AA=21
    nb_positions=16
    heat_map=np.zeros((nb_positions,nb_AA))
    for k in np.arange(nb_AA):
        # number of amino acids
        heat_map[:,k]=np.sum(ord==k,axis=0)

    frequency=(heat_map.T/np.sum(heat_map,axis=1)).T.copy()

    heat_map_plot(frequency=frequency,dir_name=dir_name,loop_nb=loop_nb)


def heat_map_plot(frequency,dir_name,loop_nb):
    'function makes heat map : curtiousy of alex :)'
    frequency = pd.DataFrame(frequency)
    frequency.columns = list("ACDEFGHIKLMNPQRSTVWXY")
    frequency['Gap'] = frequency['X']
    frequency = frequency[
        ['A', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'V', 'W', 'Y', 'Gap']]
    frequency.index = ['7', '8', '9', '9b', '9c', '10', '11', '12', '34', '35', '36', '36b', '36c', '37', '38', '39']
    for pos in ['7', '8', '9', '10', '11', '12', '34', '35', '36', '37', '38', '39']:
        frequency['Gap'][pos] = np.nan
    frequency['Aromatic (F,W,Y)'] = frequency[['F', 'W', 'Y']].mean(axis=1)
    frequency['Small (A,C,G,S)'] = frequency[['A', 'G', 'C', 'S']].mean(axis=1)
    frequency['Non-Polar Aliphatic (A,G,I,L,M,P,V)'] = frequency[['P', 'M', 'I', 'L', 'V', 'A', 'G']].mean(axis=1)
    frequency['Polar Uncharged (C,N,Q,S,T)'] = frequency[['C', 'S', 'Q', 'S', 'T']].mean(axis=1)
    frequency['Negative Charged (D,E)'] = frequency[['D', 'E']].mean(axis=1)
    frequency['Positive Charged (H,K,R)'] = frequency[['H', 'K', 'R']].mean(axis=1)
    frequency['Hydrophobic (A,F,G,I,L,M,P,V,W,Y)'] = frequency[['A', 'F', 'G', 'I', 'L', 'M', 'P', 'V', 'W', 'Y']].mean(
        axis=1)
    frequency['Hydrophilic (C,D,E,H,K,N,Q,R,S,T)'] = frequency[['C', 'D', 'E', 'H', 'K', 'N', 'Q', 'R', 'S', 'T']].mean(
        axis=1)
    frequency = frequency.transpose()
    frequency['Loop 1 (8-11)'] = frequency[['8', '9', '9b', '9c', '10', '11']].mean(axis=1)
    frequency['Loop 2 (34-39)'] = frequency[['34', '35', '36', '36b', '36c', '37', '38', '39']].mean(axis=1)
    frequency['Loop 1 & Loop 2'] = frequency[
        ['8', '9', '9b', '9c', '10', '11', '34', '35', '36', '36b', '36c', '37', '38', '39']].mean(axis=1)

    frequency = frequency[
        ['7', '8', '9', '9b', '9c', '10', '11', '12', '34', '35', '36', '36b', '36c', '37', '38', '39', 'Loop 1 (8-11)',
         'Loop 2 (34-39)', 'Loop 1 & Loop 2']]

    fig, ax = plt.subplots(1, 1, figsize=[6.5, 3], dpi=300)
    cmap = mpl.cm.Reds
    cmap.set_bad('black')

    heat_map = sns.heatmap(frequency.transpose(), square=True, vmin=0, vmax=1, cmap=cmap,
                           cbar_kws={"shrink": 0.6, "extend": 'min', "ticks": [0, 0.5, 1]})
    heat_map.figure.axes[-1].set_ylabel('Frequency', size=6)
    heat_map.figure.axes[-1].tick_params(labelsize=6)
    ax.set_yticks([x + 0.5 for x in list(range(19))])
    ax.set_yticklabels(
        ['7', '8', '9', '9b', '9c', '10', '11', '12', '34', '35', '36', '36b', '36c', '37', '38', '39', 'Loop 1 (8-11)',
         'Loop 2 (34-39)', 'Loop 1 & Loop 2'])
    ax.set_ylim([19.5, -0.5])

    ax.set_xticks([x + 0.5 for x in list(range(29))])
    pooled_AA = ['Aromatic', 'Small', 'Non-Polar Aliphatic', 'Polar Uncharged', 'Negative Charged', 'Positive Charged',
                 'Hydrophobic', 'Hydrophilic']
    ax.set_xticklabels(
        ['A', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'V', 'W', 'Y',
         'Gap'] + pooled_AA)
    ax.set_xlim([-0.5, 29.5])
    ax.tick_params(labelsize=6)
    ax.set_title('Heat map , loop %i'%(loop_nb+1))

    plt.tight_layout()
    print('saving heatmap .. '+make_file_name(dir_name=dir_name,file_description='heatmap_loop_%i'% loop_nb,fileformat='png'))
    fig.savefig(make_file_name(dir_name=dir_name,file_description='heatmap_loop_%i'% (loop_nb+1),fileformat='png'))



# unit test for making the heat map... all seemed to go well.
# seed_parent = int.from_bytes(os.urandom(4), sys.byteorder)
# g_parent = tf.random.experimental.Generator.from_seed(seed_parent)
# original_seq=pd.DataFrame()
# original_seq['Ordinal']= sm.make_sampling_data(generator=g_parent,Nb_sequences=1000,Nb_positions=16)
# os.system('mkdir ./sampling_data/test_heat_map')
# make_heat_map(df=original_seq,dir_name='test_heat_map',loop_nb=0)
