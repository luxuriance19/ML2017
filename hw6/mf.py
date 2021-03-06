from keras.models import Sequential, load_model
from keras.layers import Dense, LSTM, Embedding, Dropout, Flatten, GRU, Input, Merge
from keras.layers.core import Lambda, Activation
from keras.layers.convolutional import Conv1D
from keras.layers.pooling import MaxPooling1D
from keras.optimizers import Adam
from keras.layers.advanced_activations import LeakyReLU
from keras import backend as K
from keras.models import Model
import tensorflow as tf
from keras.backend.tensorflow_backend import set_session
from keras.layers.normalization import BatchNormalization
from keras.layers.wrappers import Bidirectional
import numpy as np
from keras.layers.merge import Concatenate
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras import layers


class MF:

    def _build_model(self, dim1, dim2, d_latent):
        print("dim1 = %d, dim2 = %d" % (dim1, dim2))
        inputs = Input(shape=(2,))

        # bias terms
        b1 = Lambda(lambda x: x[:, 0:1])(inputs)
        b1 = Embedding(dim1, 1, input_length=1)(b1)
        b1 = Flatten()(b1)

        b2 = Lambda(lambda x: x[:, 0:1])(inputs)
        b2 = Embedding(dim1, 1, input_length=1)(b2)
        b2 = Flatten()(b2)

        p = Lambda(lambda x: x[:, 0:1])(inputs)
        p = Embedding(dim1, d_latent, input_length=1)(p)
        p = Flatten()(p)

        if self.user_features is not None:
            user = Lambda(lambda x: x[:, 0:1])(inputs)
            user = Embedding(dim1, self.user_features.shape[1],
                             weights=[self.user_features],
                             input_length=1, trainable=False)(user)
            user = Flatten()(user)
            p = Concatenate()([p, user])
            p = Dense(d_latent + 1)(p)

        q = Lambda(lambda x: x[:, 1:2])(inputs)
        q = Embedding(dim2, d_latent, input_length=1)(q)
        q = Flatten()(q)

        if self.movie_features is not None:
            movie = Lambda(lambda x: x[:, 1:2])(inputs)
            movie = Embedding(dim2, self.movie_features.shape[1],
                              weights=[self.movie_features],
                              input_length=1, trainable=False)(movie)
            movie = Flatten()(movie)
            q = Concatenate()([q, movie])
            q = Dense(d_latent + 1)(q)

        x = layers.Dot(axes=1)([p, q])
        x = layers.Add()([x, b1, b2])
        self.model = Model(input=inputs, output=x)

        self.model.summary()

        optimizer = Adam(lr=self.lr, decay=self.lr_decay)

        self.model.compile(loss='mean_squared_error',
                           optimizer=optimizer,
                           metrics=['mean_squared_error'])

    def __init__(self, n_iters=100, lr=0.001,
                 lr_decay=0, batch_size=128,
                 filename=None, ram=0.2, d_latent=50,
                 user_features=None, movie_features=None):
        self.n_iters = n_iters
        self.lr = lr
        self.lr_decay = lr_decay
        self.batch_size = batch_size
        self.model = None
        self.filename = filename
        self.d_latent = d_latent
        self.user_features = user_features
        self.movie_features = movie_features

        # set GPU memory limit
        config = tf.ConfigProto()
        config.gpu_options.per_process_gpu_memory_fraction = ram
        set_session(tf.Session(config=config))

    def fit(self, X, y, valid=None):
        if self.model is None:
            self._build_model(np.max(X[:, 0]) + 1,
                              np.max(X[:, 1]) + 1,
                              self.d_latent)

        if valid is not None:
            valid = (valid['x'], valid['y'])

        earlystopping = EarlyStopping(monitor='val_mean_squared_error',
                                      patience=15,
                                      mode='min')

        checkpoint = ModelCheckpoint(filepath=self.filename,
                                     verbose=1,
                                     save_best_only=True,
                                     monitor='val_mean_squared_error',
                                     mode='min')

        self.model.fit(X, y,
                       epochs=self.n_iters,
                       validation_data=valid,
                       batch_size=self.batch_size,
                       callbacks=[earlystopping, checkpoint])

    def load(self, filename):
        self.model = load_model(filename)

    def predict_raw(self, X):
        return self.model.predict(X)

    def predict(self, X, threshold=0.5):
        predict = self.model.predict(X)
        return np.where(predict > threshold, 1, 0)
