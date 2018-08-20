from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf

class ResNetBase(object):
    def __init__(self, is_training, data_format, batch_norm_decay,
                 batch_norm_epsilon):
        self._batch_norm_decay = batch_norm_decay
        self._batch_norm_epsilon = batch_norm_epsilon
        self._is_training = is_training
        assert data_format in ('channels_first', 'channels_last')
        self._data_format = data_format

    def forward_pass(self, x):
        msg = 'forward_pass() is implemented in ResNetBase sub classes'
        raise NotImplementedError(msg)

    def _residual_v1(self, x, kernel_size, in_filter, out_filter, stride,
                     activate_before_residual=False):
        del activate_before_residual
        with tf.name_scope('residual_v1') as name_scope:
            orig_x = x

            x = self._conv(x, kernel_size, out_filter, stride)
            x = self._batch_norm(x)
            x = self._relu(x)

            x = self._conv(x, kernel_size, out_filter, 1)
            x = self._batch_norm(x)

            if in_filter != out_filter:
                orig_x = self._avg_pool(orig_x, stride, stride)
                pad = (out_filter - in_filter) // 2
                if self._data_format == 'channels_first':
                    pad_pattern = [[0, 0], [pad, pad], [0, 0], [0, 0]]
                else:
                    pad_pattern = [[0, 0], [0, 0], [0, 0], [pad, pad]]
                orig_x = tf.pad(orig_x, pad_pattern)

            x = self._relu(tf.add(x, orig_x))

            tf.logging.info('image after unit %s: %s', name_scope, x.get_shape())
            return x

    def _residual_v2(self, x, in_filter, out_filter, stride,
                     activate_before_residual=False):
        with tf.name_scope('residual_v2') as name_scope:
            if activate_before_residual:
                x = self._batch_norm(x)
                x = self._relu(x)
                orig_x = x
            else:
                orig_x = x
                x = self._batch_norm(x)
                x = self._relu(x)

            x = self._conv(x, 3, out_filter, stride)

            x = self._batch_norm(x)
            x = self._relu(x)
            x = self._conv(x, 3, out_filter, [1, 1, 1, 1])

            if in_filter != out_filter:
                pad = (out_filter - in_filter) // 2
                orig_x = self._avg_pool(orig_x, stride, stride)
                if self._data_format == 'channels_first':
                    pad_pattern = [[0, 0], [pad, pad], [0, 0], [0, 0]]
                else:
                    pad_pattern = [[0, 0], [0, 0], [0, 0], [pad, pad]]
                orig_x = tf.pad(orig_x, pad_pattern)

            x = tf.add(x, orig_x)

            log = 'image after unit %s: %s', name_scope, x.get_shape()
            tf.logging.info(log)
            return x

    def _bottleneck_residual_v2(self, x, in_filter, out_filter, stride,
                                activate_before_residual=False):
        with tf.name_scope('bottle_residual_v2') as name_scope:
            if activate_before_residual:
                x = self._batch_norm(x)
                x = self._relu(x)
                orig_x = x
            else:
                orig_x = x
                x = self._batch_norm(x)
                x = self._relu(x)

            x = self._conv(x, 1, out_filter // 4, stride, is_atrous=True)
            x = self._batch_norm(x)
            x = self._relu(x)
            x = self._conv(x, 3, out_filter // 4, 1, is_atrous=True)

            x = self._batch_norm(x)
            x = self._relu(x)
            x = self._conv(x, 1, out_filter, 1, is_atrous=True)

            if in_filter != out_filter:
                orig_x = self._conv(orig_x, 1, out_filter, stride,
                                    is_atrous=True)
            x = tf.add(x, orig_x)

            log = 'image after unit %s: %s', name_scope, x.get_shape()
            tf.logging.info(log)
            return x

    def _conv(self, x, kernel_size, filters, strides, is_atrous=False):
        padding = 'SAME' #used to be SAME
        if not is_atrous and strides > 1:
            pad = kernel_size - 1
            beg = pad // 2
            end = pad - beg
            if self._data_format == 'channels_first':
                pad_pattern = [[0, 0], [0, 0], [beg, end], [beg, end]]
            else:
                pad_pattern = [[0, 0], [beg, end], [beg, end], [0, 0]]
            x = tf.pad(x, pad_pattern)
            padding = 'VALID'

        return tf.layers.conv2d(inputs=x, kernel_size=kernel_size,
                                filters=filters, strides=strides,
                                padding=padding, use_bias=False,
                                data_format=self._data_format)
    def _batch_norm(self, x):
        if self._data_format == 'channels_first':
            data_format = 'NCHW'
        else:
            data_format = 'NHWC'
        return tf.contrib.layers.batch_norm(x, decay=self._batch_norm_decay,
                                            center=True, scale=True,
                                            epsilon=self._batch_norm_epsilon,
                                            is_training=self._is_training,
                                            fused=True,
                                            data_format=data_format)

    def _relu(self, x):
        return tf.nn.relu(x)

    def _fully_connected(self, x, out_dim):
        with tf.name_scope('fully_connected') as name_scope:
            x = tf.layers.dense(x, out_dim)
            return x

        msg = 'image after unit %s: %s', name_scope, x.get_shape()
        tf.logging.info(msg)

    def _avg_pool(self, x, pool_size, stride):
        with tf.name_scope('avg_pool') as name_scope:
            x = tf.layers.average_pooling2d(x, pool_size, stride, 'SAME',
                    data_format=self._data_format)

        msg = 'image after unit %s: %s', name_scope, x.get_shape()
        tf.logging.info(msg)
        return x

    def _global_avg_pool(self, x):
        with tf.name_scope('global_avg_pool') as name_scope:
            assert x.get_shape().ndims == 4
            if self._data_format == 'channels_first':
                x = tf.reduce_mean(x, [2, 3])
            else:
                x = tf.reduce_mean(x, [1, 2])
        msg = 'image after unit %s: %s', name_scope, x.get_shape()
        tf.logging.info(msg)
        return x