from deepdab.ai import *
from deepdab import *
import tensorflow as tf
import numpy as np
from deepdab.util.initializer_util import *


class TDOneGradientPolicyCNN(Policy):
    def __init__(self, board_size, existing_params=None):
        self._board_size = board_size

        edge_matrix = init_edge_matrix(board_size)
        self._n_input_rows = edge_matrix.shape[0]
        self._n_input_cols = edge_matrix.shape[1]
        self._n_hidden = 300
        self._n_filters = 12
        self._n_output = 1

        # TF graph creation
        g = tf.Graph()
        with g.as_default():
            self._input = tf.placeholder("float", [self._n_input_rows, self._n_input_cols], name="input")
            self._target = tf.placeholder("float", [1, self._n_output], name="target")
            self._error = tf.placeholder("float", shape=[], name="error")
            self._lr = tf.placeholder("float", shape=[], name="learning_rate")
            self._sum_grad_W_in = tf.placeholder("float", shape=[3 * 3 * self._n_filters, self._n_hidden], name="sum_grad_W_in")
            self._sum_grad_b_in = tf.placeholder("float", shape=[self._n_hidden], name="sum_grad_b_in")
            self._sum_grad_W_out = tf.placeholder("float", shape=[self._n_hidden, 1], name="sum_grad_W_out")
            self._sum_conv2d_kernel = tf.placeholder("float", shape=[3, 3, 1, self._n_filters], name="sum_conv2d_kernel")
            self._sum_conv2d_bias = tf.placeholder("float", shape=[self._n_filters], name="sum_conv2d_bias")

            W_in_initializer = existing_param_initializer(existing_params, "W_in", tf.random_normal_initializer(0.0, 0.1))
            b_in_initializer = existing_param_initializer(existing_params, "b_in", tf.zeros_initializer())
            W_out_initializer = existing_param_initializer(existing_params, "W_out", tf.random_normal_initializer(0.0, 0.1))
            conv_kernel_initializer = existing_param_initializer(existing_params, "conv2d/kernel:0", tf.random_normal_initializer(0.0, 0.1))
            conv_bias_initializer = existing_param_initializer(existing_params, "conv2d/bias:0", tf.zeros_initializer())

            self._W_in = tf.get_variable(shape=[3 * 3 * self._n_filters, self._n_hidden], initializer=W_in_initializer, name="W_in")
            self._b_in = tf.get_variable(shape=[self._n_hidden], initializer=b_in_initializer, name="b_in")
            self._W_out = tf.get_variable(shape=[self._n_hidden, self._n_output], initializer=W_out_initializer, name="W_out")

            self._input_reshaped = tf.reshape(self._input, shape=[1, self._n_input_rows, self._n_input_cols, 1])

            # Convolutional Layer
            # Computes N features using a 3x3 filter with ReLU activation.
            # No padding is added.
            # Input Tensor Shape (for the 2x2 board): [1, 5, 5, 1] (batch size, width, height, channels)
            # Output Tensor Shape: [1, 3, 3, N]
            self._conv = tf.layers.conv2d(
                inputs=self._input_reshaped,
                filters=self._n_filters,
                kernel_size=[3, 3],
                strides=(1, 1),
                kernel_initializer=conv_kernel_initializer,
                bias_initializer=conv_bias_initializer,
                activation=tf.nn.relu)

            self._conv_flat = tf.reshape(self._conv, [1, 3 * 3 * self._n_filters])

            dense_layer = tf.nn.tanh(tf.matmul(self._conv_flat, self._W_in) + self._b_in)

            self._prediction = tf.nn.sigmoid(tf.matmul(dense_layer, self._W_out))

            self._conv2d_kernel = [v for v in tf.global_variables() if v.name == 'conv2d/kernel:0'][0]
            self._conv2d_bias = [v for v in tf.global_variables() if v.name == 'conv2d/bias:0'][0]

            self._gradients = tf.gradients(self._prediction, [self._W_in, self._b_in, self._W_out,
                                                              self._conv2d_kernel, self._conv2d_bias])

            self._update_W_in = self._W_in.assign(self._W_in + self._lr * self._error * self._sum_grad_W_in)
            self._update_b_in = self._b_in.assign(self._b_in + self._lr * self._error * self._sum_grad_b_in)
            self._update_W_out = self._W_out.assign(self._W_out + self._lr * self._error * self._sum_grad_W_out)
            self._update_conv2d_kernel = self._conv2d_kernel.assign(self._conv2d_kernel + self._lr * self._error * self._sum_conv2d_kernel)
            self._update_conv2d_bias = self._conv2d_bias.assign(self._conv2d_bias + self._lr * self._error * self._sum_conv2d_bias)

        # TF session creation and initialization
        self._sess = tf.Session(graph=g)
        with g.as_default():
            self._sess.run(tf.global_variables_initializer())

        self.reset_history()

    def get_architecture(self):
        return "5x5-conv(%sx%s, relu, %s)-tanh(%s)-sigmoid(1)" % (3, 3, self._n_filters, self._n_hidden)

    def reset_history(self):
        self._prediction_history = []
        self._prediction_gradient_history = []

    def select_edge(self, board_state):
        if self._softmax_action:
            return self._select_edge_softmax(board_state)
        else:
            return self._select_edge_epsilon_greedily(board_state)

    def _select_edge_softmax(self, board_state):
        softmax = lambda x, T : np.exp(x/T)/np.sum(np.exp(x/T))
        zero_indices = []
        for i in range(len(board_state)):
            if board_state[i] == 0:
                zero_indices.append(i)
        new_state_values = []
        new_state_gradients = []
        for zero_index in zero_indices:
            new_state = [x for x in board_state]
            new_state[zero_index] = 1
            new_state = convert_board_state_to_edge_matrix(self._board_size, new_state)
            new_state_value, gradients = self._sess.run([self._prediction, self._gradients],
                                                        feed_dict={self._input: new_state})
            new_state_values.append(new_state_value[0][0])
            new_state_gradients.append(gradients)
        choices = range(len(new_state_values))
        selected_index = np.random.choice(choices, p=softmax(np.array(new_state_values), self._temperature))
        if self._store_history:
            self._prediction_history.append(new_state_values[selected_index])
            self._prediction_gradient_history.append(new_state_gradients[selected_index])
        return zero_indices[selected_index]

    def _select_edge_epsilon_greedily(self, board_state):
        zero_indices = []
        for i in range(len(board_state)):
            if board_state[i] == 0:
                zero_indices.append(i)
        if random.random() < self._epsilon:
            chosen_index = random.choice(zero_indices)
            if self._store_history:
                new_state = [x for x in board_state]
                new_state[chosen_index] = 1
                new_state = convert_board_state_to_edge_matrix(self._board_size, new_state)
                new_state_value, gradients = self._sess.run([self._prediction, self._gradients],
                                                            feed_dict={self._input: new_state})
                self._prediction_history.append(new_state_value[0][0])
                self._prediction_gradient_history.append(gradients)
            return chosen_index
        else:
            best_value = 0.0
            best_value_gradient = None
            best_state_index = zero_indices[0]
            for zero_index in zero_indices:
                new_state = [x for x in board_state]
                new_state[zero_index] = 1
                new_state = convert_board_state_to_edge_matrix(self._board_size, new_state)
                new_state_value, gradients = self._sess.run([self._prediction, self._gradients],
                                                            feed_dict={self._input: new_state})
                if new_state_value >= best_value:
                    best_value = new_state_value
                    best_value_gradient = gradients
                    best_state_index = zero_index
            if self._store_history:
                self._prediction_history.append(best_value[0][0])
                self._prediction_gradient_history.append(best_value_gradient)
            return best_state_index

    def set_should_store_history(self, store_history):
        self._store_history = store_history

    def get_epsilon(self):
        return self._epsilon

    def set_epsilon(self, eps):
        self._epsilon = eps

    def get_learning_rate(self):
        return self._learning_rate

    def set_learning_rate(self, lr):
        self._learning_rate = lr

    def get_temperature(self):
        return self._temperature

    def set_temperature(self, temp):
        self._temperature = temp

    def is_softmax_action(self):
        return self._softmax_action

    def set_softmax_action(self, is_softmax_action):
        self._softmax_action = is_softmax_action

    def update(self):
        if len(self._prediction_history) > 1:
            error = self._prediction_history[-1] - self._prediction_history[-2]
            sum_grad_W_in = np.sum(self._prediction_gradient_history[:-1], axis=0)[0]
            sum_grad_b_in = np.sum(self._prediction_gradient_history[:-1], axis=0)[1]
            sum_grad_W_out = np.sum(self._prediction_gradient_history[:-1], axis=0)[2]
            sum_conv2d_kernel = np.sum(self._prediction_gradient_history[:-1], axis=0)[3]
            sum_conv2d_bias = np.sum(self._prediction_gradient_history[:-1], axis=0)[4]
            self._sess.run([self._update_W_in, self._update_b_in, self._update_W_out,
                            self._update_conv2d_kernel, self._update_conv2d_bias],
                           feed_dict={self._lr: self._learning_rate, self._error: error,
                                      self._sum_grad_W_in: sum_grad_W_in, self._sum_grad_b_in: sum_grad_b_in,
                                      self._sum_grad_W_out: sum_grad_W_out, self._sum_conv2d_kernel: sum_conv2d_kernel,
                                      self._sum_conv2d_bias: sum_conv2d_bias})

    def update_terminal(self, target):
        error = target - self._prediction_history[-1]
        sum_grad_W_in = np.sum(self._prediction_gradient_history, axis=0)[0]
        sum_grad_b_in = np.sum(self._prediction_gradient_history, axis=0)[1]
        sum_grad_W_out = np.sum(self._prediction_gradient_history, axis=0)[2]
        sum_conv2d_kernel = np.sum(self._prediction_gradient_history, axis=0)[3]
        sum_conv2d_bias = np.sum(self._prediction_gradient_history, axis=0)[4]
        self._sess.run([self._update_W_in, self._update_b_in, self._update_W_out,
                        self._update_conv2d_kernel, self._update_conv2d_bias],
                       feed_dict={self._lr: self._learning_rate, self._error: error,
                                  self._sum_grad_W_in: sum_grad_W_in, self._sum_grad_b_in: sum_grad_b_in,
                                  self._sum_grad_W_out: sum_grad_W_out, self._sum_conv2d_kernel: sum_conv2d_kernel,
                                  self._sum_conv2d_bias: sum_conv2d_bias})

    def update_offline(self, target):
        if len(self._prediction_history) > 0:
            for i in range(1, len(self._prediction_history) + 1):
                prev = self._prediction_history[i - 1]
                last = self._prediction_history[i] if i < len(self._prediction_history) else target
                error = last - prev
                sum_grad_W_in = np.sum(self._prediction_gradient_history[:i], axis=0)[0]
                sum_grad_b_in = np.sum(self._prediction_gradient_history[:i], axis=0)[1]
                sum_grad_W_out = np.sum(self._prediction_gradient_history[:i], axis=0)[2]
                sum_conv2d_kernel = np.sum(self._prediction_gradient_history[:i], axis=0)[3]
                sum_conv2d_bias = np.sum(self._prediction_gradient_history[:i], axis=0)[4]
                self._sess.run([self._update_W_in, self._update_b_in, self._update_W_out,
                                self._update_conv2d_kernel, self._update_conv2d_bias],
                               feed_dict={self._lr: self._learning_rate, self._error: error,
                                          self._sum_grad_W_in: sum_grad_W_in, self._sum_grad_b_in: sum_grad_b_in,
                                          self._sum_grad_W_out: sum_grad_W_out, self._sum_conv2d_kernel: sum_conv2d_kernel,
                                          self._sum_conv2d_bias: sum_conv2d_bias})

    def get_params(self):
        params_map = {}
        params = self._sess.run([self._W_in])
        params_map["W_in"] = params[0].tolist()
        params = self._sess.run([self._b_in])
        params_map["b_in"] = params[0].tolist()
        params = self._sess.run([self._W_out])
        params_map["W_out"] = params[0].tolist()
        params = self._sess.run([self._conv2d_kernel])
        params_map["conv2d/kernel:0"] = params[0].tolist()
        params = self._sess.run([self._conv2d_bias])
        params_map["conv2d/bias:0"] = params[0].tolist()
        return params_map

    def copy(self):
        policy_copy = type(self)(self._board_size, self.get_params())
        policy_copy.set_temperature(self.get_temperature())
        policy_copy.set_softmax_action(self.is_softmax_action())
        policy_copy.set_epsilon(self.get_epsilon())
        policy_copy.set_should_store_history(False)
        return policy_copy

    def print_params(self, f):
        params = self._sess.run([self._W_in])
        f.write("W_in: %s\n" % params[0].tolist())
        params = self._sess.run([self._b_in])
        f.write("b_in: %s\n" % params[0].tolist())
        params = self._sess.run([self._W_out])
        f.write("W_out: %s\n" % params[0].tolist())
        params = self._sess.run([self._conv2d_kernel])
        f.write("conv2d_kernel: %s\n" % params[0].tolist())
        params = self._sess.run([self._conv2d_bias])
        f.write("conv2d_bias: %s\n" % params[0].tolist())

    def print_gradients(self):
        print(self._prediction_gradient_history)
