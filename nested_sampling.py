import time
import submodels_module as mb
import load_format_data
import pandas as pd
import numpy as np
import tensorflow as tf
import os
import sys
from abc import ABC, abstractmethod
import matplotlib.pyplot as plt
import scipy.sparse as sparse


class nested_sampling(ABC):
    # main method is to call is walk()
    def __init__(self, s2a_params=None, e2y_params=None, Nb_sequences=1000):
        # initilize default model parameters
        if e2y_params is None:
            e2y_params = ['svm', 1]
        if s2a_params is None:
            s2a_params = [[1, 8, 10], 'emb_cnn', 1]

        # note: things may change between tensorflow versions
        self.g_parent = tf.random.experimental.Generator.from_seed(seed_parent)

        df = self.g_parent.uniform(shape=[Nb_sequences, 16], minval=0, maxval=21, dtype=tf.int64).numpy()
        # else :
        # make a random distribution for N number of sequences
        # hold the original sequence
        self.original_seq = df[['Ordinal']]
        self.nb_of_sequences = Nb_sequences
        print('copying orginal sequence ordinals to test sequence')
        self.test_seq = self.original_seq.copy()
        self.original_seq['Developability'] = np.zeros(self.nb_of_sequences)
        # self.nb_of_sequences,_=np.shape(self.original_seq['Ordinal'])

        self.s2a = mb.seq_to_assay_model(*s2a_params)
        # i'm putting zero here b/c it requires a parameter...
        self.e2y = mb.sequence_embeding_to_yield_model(s2a_params + [0], *e2y_params)
        self.times = pd.DataFrame()
        self.start_time = None
        self.min_yield = []
        # parent random number generator
        self.vp = []
        self.percent_pos = []
        self.vp_step = []

    def nested_sample(self, N_loops=10, N_steps=10, write2pickle=True, steps_2_show=None, loops_2_show=None):
        'main method to call, does nested sampling'
        # TODO: describe what the inputs should be ...
        # this is the loop I would like to have done by the end of today. So that a driver script can just call this
        # method an all will be good.
        # write2pickle is a boolean flag to see where optimized sequences should be written too.
        if steps_2_show is None:
            # default is to show 3 plots
            steps_2_show = np.array([0, N_steps // 2, N_steps])
        if loops_2_show is None:
            # default is to show 3 loops
            loops_2_show = np.array([0, N_loops // 2, N_loops])

        # TODO: error checking for steps and loops to show?
        self.init_violin_plots(loops_2_show=loops_2_show)
        # self.init_step_plots(steps_2_show=steps_2_show)

        # TODO: figure out the orginal_seq and test_seq craziness... honestly test sequence
        #  should just be a local parameter to the walk. not a local to the class one... that would look much better ..

        # get yield should have an input parameter
        for j in np.arange(N_loops):
            print('LOOP %i of %i loops' % (j, N_loops))
            self.init_walk(j=j, steps_2_show=steps_2_show, loops_2_show=loops_2_show)
            self.walk(min_yield=self.min_yield[-1], steps_2_show=steps_2_show, j=j, N_steps=N_steps,
                      loops_2_show=loops_2_show, N_loops=N_loops)  # default is N=10
            _, idx = self.update_min_yield(self.original_seq)
            self.change_lowest_yield_sequence_configuration(idx)  # change to another sequence in the configuration

        # TODO: plot the rate of change of min yield as well ...
        self.make_min_yield_plot(N_loops=N_loops, N_steps=N_steps)

        self.make_percent_positive_plot(N_steps=N_steps, N_loops=N_loops)
        # TODO: write 2 pickle file the best sequences ...
        # TODO: heat map for the best sequences
        print(self.times)

    @abstractmethod
    def walk(self, min_yield, steps_2_show, N_loops, loops_2_show, N_steps=10, j=1):
        'abstract method, must define in sublclass how to walk/mutate'
        pass

    def make_min_yield_plot(self, N_loops, N_steps):
        plt.plot(np.arange(N_loops + 1).tolist(), self.min_yield)
        plt.title('min yield vs. nb of loops')
        plt.ylabel('min yield')
        plt.xlabel('nb of loops')
        plt.savefig('./figures/min_yield/min_yield_Nbsteps_%i_Nb_loops_%i.png' % (N_steps, N_loops))
        plt.close()

    def make_percent_positive_plot(self, N_loops, N_steps):
        pp = []
        for i in np.arange(N_loops):
            pp.append(self.percent_pos[i][0])
        plt.plot(np.arange(N_loops).tolist(), pp)
        plt.title('percent accepted vs. for each loop')
        plt.ylabel('percent accepted')
        plt.xlabel('# of loops')
        plt.savefig('./figures/percent_pos/percent_pos_Nbsteps_%i_Nb_loops_%i.png' % (N_steps, N_loops))
        plt.close()

    def init_walk(self, j, steps_2_show, loops_2_show):
        # i should always be equal to zero here
        if j == 0:
            print('finding min yield of init sequences')
            self.original_seq = self.get_yield().copy()
            self.update_min_yield(self.original_seq)
        if j in loops_2_show and 0 in steps_2_show:
            self.plot_violin(i=0, j=j, seq=self.original_seq, loops_2_show=loops_2_show, steps_2_show=steps_2_show)

    # private methods
    def get_yield(self):
        'gets the predicted yield from a model'
        df_with_embbeding = self.s2a.save_sequence_embeddings(df_list=[self.test_seq], is_ordinals_only=True)

        predicted_yield_per_model = []
        for i in np.arange(3):
            predicted_yield_per_model.append(
                self.e2y.save_predictions(df=df_with_embbeding, df_emb=True, sampling_nb=i))
        self.test_seq['Developability'] = np.copy(np.average(predicted_yield_per_model, axis=0))
        return self.test_seq

    def update(self, min_yield):
        'updates the sequences based on if they are higher than the last minimum yield'
        print('updating the sequences based on last minimum yield')
        print('current minimum yield is  %0.2f' % min_yield)
        # convert the pandas columns to numpy arrays so no for loops  :/
        orginal_array, test_array, test_dev, org_dev = self.convert2numpy()

        # accept changes that meet the min yield requirement
        mutatable_seq = min_yield < test_dev
        orginal_array[mutatable_seq, :] = np.copy(test_array[mutatable_seq, :])
        org_dev[mutatable_seq] = np.copy(test_dev[mutatable_seq])
        # update self.test_seq and self.original_seq
        # dangerous code below ; changing self parameters...

        self.save_testseq_2_original_seq(org_dev, orginal_array)
        # i really need to make some error checking statements
        # return percentage positive
        return np.count_nonzero(mutatable_seq) / mutatable_seq.shape[0]

    def save_testseq_2_original_seq(self, org_dev, orginal_array):
        print('Saving the updated sequence and developability of last sequence as well.')
        # have to make list of tuples
        org_list = []
        for i in orginal_array:
            org_list.append((i))  # this is a tuple with length 1 of a ndarray (numpy)
        self.original_seq['Ordinal'] = org_list
        self.original_seq['Developability'] = org_dev
        print('updating new test seq. ')
        self.original_seq = self.original_seq[['Ordinal', 'Developability']]
        self.test_seq = self.original_seq.copy()
        self.test_seq = self.test_seq[['Ordinal']]

    def convert2numpy(self):
        test_array = np.copy(np.array(self.test_seq['Ordinal'].to_numpy().tolist()))
        orginal_array = np.copy(np.array(self.original_seq['Ordinal'].to_numpy().tolist()))
        test_dev = np.copy(self.test_seq['Developability'].to_numpy())
        org_dev = np.copy(self.original_seq['Developability'].to_numpy())
        return orginal_array, test_array, test_dev, org_dev

    def start_timer(self):
        print('starting timer')
        self.start_time = time.time()

    def stop_timer(self, loops_2_show, j, i=None, ):
        print('stop timer')
        stop_time = time.time() - self.start_time
        if j in loops_2_show:
            self.times.loc[i, str(j) + 'th loop'] = stop_time

    def update_min_yield(self, seq):
        print('update the minimum yield.. updating self.min_yield %0.2f' % np.min(
            seq['Developability'].to_numpy().tolist()))
        # consider making the update of the min yield...
        self.min_yield.append(np.min(seq['Developability'].to_numpy().tolist()))

        # return the last element in the sequence
        return self.min_yield[-1], np.argmin(seq['Developability'].to_numpy().tolist())

    def change_lowest_yield_sequence_configuration(self, idx):
        print('resampling sequence with lowest min yield, seq idx: %i' % idx)
        change_2_seq = idx
        # idk if any of those syntax is correct ...
        # TODO : check to make sure lowest yield in sequence is being changed correctly
        while change_2_seq == idx:
            change_2_seq = \
                self.g_parent.uniform(shape=[1], minval=0, maxval=self.nb_of_sequences,  # [0,nb_of_sequences)
                                      dtype=tf.int64).numpy()[0]

        # just do the normal method here b/c this is being dumb.
        orginal_array = np.copy(np.array(self.original_seq['Ordinal'].to_numpy().tolist()))
        orginal_array[idx, :] = orginal_array[change_2_seq, :].copy()
        # TODO: optimize in pandas
        org_list = []
        for i in orginal_array:
            org_list.append((i))  # this is a tuple with length 1 of a ndarray (numpy)
        self.original_seq['Ordinal'] = org_list
        print('updated lowest min yield')
        # retrun the arg min for the lowest developability

    def init_violin_plots(self, loops_2_show):
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

    def close_violin(self, j, steps_2_show, loops_2_show, Nb_steps, Nb_loops):
        v = self.vp[np.argmax(loops_2_show == j)]
        str_steps_2_show = []
        for i in steps_2_show:
            if i == 0:
                str_steps_2_show.append('Init')
            else:
                str_steps_2_show.append('step:%i,percent:%0.2f' % (i, self.percent_pos[j][i - 1]))
        fig = v[0]
        ax = v[1]
        ax.set_xticks(np.arange(len(steps_2_show)))
        ax.set_ylim([-1, 1.5])
        ax.set_xticklabels(str_steps_2_show)
        ax.set_ylabel('Yield', fontsize=6)
        ax.tick_params(axis='both', which='major', labelsize=6)
        ax.set_title('Loop %i of %i' % (j + 1, Nb_loops))
        ax.axhline(self.min_yield[j]).set_color('r')
        fig.tight_layout()
        print('saving ./figures/loop_violin/distribution_Nbsteps_%i_Nb_loops_%i_loop_%i.png' % (Nb_steps, Nb_loops, j))
        fig.savefig('./figures/loop_violin/distribution_Nbsteps_%i_Nb_loops_%i_loop_%i.png' % (Nb_steps, Nb_loops, j))
        plt.close(fig)


class ns_random_sample(nested_sampling):
    # nested sampling random sampling implementation.
    def __init__(self):
        super().__init__()
        # initilize generator
        seed = int.from_bytes(os.urandom(4), sys.byteorder)
        # note: things may change between tensorflow versions
        self.g = tf.random.experimental.Generator.from_seed(seed)

    def walk(self, min_yield, steps_2_show, loops_2_show, N_loops, N_steps=10, j=1):

        # here make min_yield a local parameter,  it is required
        # N is the number of iterations , can update in the future to do an actual convergence algorithm
        # i and j represent the histogram to plot too. default is just a single walk.
        percent_pos = []
        for i in np.arange(N_steps):
            print('loop %i of %i, step %i of %i' % (j + 1, N_loops, i + 1, N_steps))
            self.start_timer()
            self.mutate()
            self.test_seq = self.test_seq[['Ordinal']]
            print('getting yield')
            self.get_yield()
            pp = self.update(min_yield)
            percent_pos.append(pp)
            # self.check()
            self.stop_timer(j=j, i=i, loops_2_show=loops_2_show)
            if i + 1 in steps_2_show and j in loops_2_show:
                self.plot_violin(i=i + 1, j=j, seq=self.original_seq, steps_2_show=steps_2_show,
                                 loops_2_show=loops_2_show)
        self.percent_pos.append(percent_pos)
        if j in loops_2_show:
            self.close_violin(j=j, steps_2_show=steps_2_show, loops_2_show=loops_2_show, Nb_loops=N_loops,
                              Nb_steps=N_steps)

    # def check(self):
    #     orginal_array = np.copy(np.array(self.original_seq['Ordinal'].to_numpy().tolist()))
    #     org_dev = np.copy(self.original_seq['Developability'].to_numpy())
    #     if (org_dev < self.min_yield[-1]):
    #         raise ValueError
    #

    def plot_hist(self, i, j, seq):
        # future version
        print('Plotting histogram Step:%i,Loop%i' % (i, j))

        plt.hist(seq['Developability'].to_numpy(), bins=50)
        plt.title('Step: %i Ns: %i threshold yield: %0.2f'
                  % (i, j, self.min_yield[-1]))
        plt.ylabel('frequency')
        plt.xlabel('yield')
        plt.savefig('./figures/sampling_figs/step%i_loop%i.png' % (i, j))
        plt.close()

    def mutate(self):
        'mutate the sequences where necessary, this is a random mutation'
        # mutate every sequence of the original
        # for a mutation to occur ;
        # pseudo random number
        # generate a pseudo random number to define which AA to change [0-15]
        random_AA_pos = self.g.uniform(shape=[self.nb_of_sequences], minval=0, maxval=16,
                                       dtype=tf.int64).numpy()  # [0,16)
        # generate a pseudo random number to define which AA to change to [0-20]
        # using the same generator might be problematic
        random_AA = self.g.uniform(shape=[self.nb_of_sequences], minval=0, maxval=21, dtype=tf.int64).numpy()
        # [0,21)
        # remove blanks from the sequence
        test_numpy_seq = np.copy(np.array(self.test_seq['Ordinal'].to_numpy().tolist()))
        random_AA = self.remove_blanks(random_AA_pos, random_AA, test_numpy_seq)
        print('mutating test sequence')
        # converting to numpy for logical array manipulation
        # test_numpy_seq[:, random_AA_pos] = random_AA
        # there has to be a way to do this without a loop.

        test_list_seq = []
        for j, r_AA, r_AA_pos, i in zip(test_numpy_seq, random_AA, random_AA_pos, np.arange(test_numpy_seq.shape[0])):
            j[r_AA_pos] = r_AA
            test_list_seq.append((j))
        self.test_seq['Ordinal'] = test_list_seq

    def incorrect_blanks(self, random_AA, random_AA_pos, seq):
        # make sure that its in position 3,4,11,12
        # and if its in position 4,
        # make sure 3 is 19 otherwise resample
        # and if its in position 12,
        # make sure 11 is 19 otherwise resample

        # test
        # random_AA = np.array([19, 19, 19, 19])
        # random_AA_pos = np.array([3, 4, 11,12])
        # seq = np.zeros((4, 16))
        # seq[0,3]=19
        # seq[1,3]=19
        # seq[2,11]=19
        # seq[3,11]=19

        change_blanks = np.bitwise_and(random_AA == 19,
                                       np.bitwise_or(
                                           np.bitwise_and(
                                               np.bitwise_and(random_AA_pos != 4, random_AA_pos != 3),
                                               np.bitwise_and(random_AA_pos != 11, random_AA_pos != 12)
                                           ),  # check for special corrrections
                                           np.bitwise_or(np.bitwise_and(random_AA_pos == 3, seq[:, 4] != 19),
                                                         np.bitwise_and(random_AA_pos == 11, seq[:, 12] != 19))))
        return change_blanks

    def remove_blanks(self, random_AA_pos, random_AA, seq):
        'removes blanks by resampling'
        # seq is a numpy 2D array of sequences.
        print('helper function to remove blanks')

        # so i'm staying in the same spot im just resampling if we artest_array[:, random_AA_pos]e in a blank space
        # while any of the sequences are 19 (i.e. the blank space)
        change_blanks = self.incorrect_blanks(random_AA, random_AA_pos, seq)
        while change_blanks.any():
            size = np.count_nonzero(change_blanks)
            print('change these blanks %i' % size)
            new_random_AA = self.g.uniform(
                shape=[size], minval=0, maxval=21, dtype=tf.int64).numpy()
            random_AA[change_blanks] = new_random_AA
            change_blanks = self.incorrect_blanks(random_AA, random_AA_pos, seq)
        return random_AA


def driver():
    # this is code to just go for a walk
    trial1 = ns_random_sample()
    # first_seqeunce = trial1.get_yield()
    # min_yield_start , _= trial1.update_min_yield(first_seqeunce)
    # trial1.plot_hist(0, 1,first_seqeunce)
    # trial1.walk(min_yield=min_yield_start)
    trial1.nested_sample()
    # trial1.nested_sample()


driver()
# set ord to a random configuration
# intilize the sequence to assay model (with the s2a_parameters
# intilize the sequence embedding to yield models  (e2y_parameters)
# e2y=mb.sequence_embeding_to_yield_model(s2a_params,*e2y_params)
# initilize the old ordinals to None
# until convergence
# for i in np.arange(N):
#     # for 3 models get the embedding
#     #       call seq to assay. save embeddings for a df with just the ordinals (Return a data frame with a new column
#     #       called learned embeddings
#     df_emb=s2a.save_sequence_embeddings(ord, True)
#     for j in np.arange(3):
# #       call seq embedding to yield. save_predictions for df_emb
#         df_predict=e2y.save_predictions()
#
#         avg_predictions()
# #       average the predictions
# #   update the dataframes for accepted mutations unless it is the first go around, update the lowest allowed
# #   yield as well.
# #   mutate the ordinals, and pass that as the new dataframe into as the new predict yield
# def __plot_histogram(self):
# keep adding columns to histogram
# then at the end show histogram and save
# def __save_attributes(self):
# save the histogram and pickle file
#
#     update min yield between random walks
#     actually maybe this should be a driver script...
#     def sample(self):
#       main method for nested sampling.
#       would have continous calls to walk
#       then update min yield after walking
#       then a call to plot histogram for another violin plot attribute
# special corrections
# only look at sequences with a random AA position of 4 or 12 with random_AA of 19
# check_again = np.bitwise_and(np.bitwise_or(random_AA_pos == 4, random_AA_pos == 12), random_AA == 19

# for single_sequence, change_blank, r_AA in zip(seq[check_again, :], change_blanks[check_again],
#                                                random_AA_pos[check_again]):
#     # check to make sure the previous positions are correct
#     if (single_sequence[2] is not 19 and r_AA is 4) or (single_sequence[10] is not 19 and r_AA is 12):
#         change_blank = True


# def init_step_plots(self,steps_2_show):
#     nb_violinplots = len(steps_2_show)
#     for k in np.arange(nb_violinplots):
#         self.vp_step.append(plt.subplots(1, 1, figsize=[5, 3], dpi=300))
#     return self.vp_step