import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchrl.networks.init as init


class ZeroNet(nn.Module):
    def forward(self, x):
        """
        Forward computation.

        Args:
            self: (todo): write your description
            x: (todo): write your description
        """
        return torch.zeros(1)


class Net(nn.Module):
    def __init__(
            self,
            output_shape,
            base_type,
            append_hidden_shapes=[],
            append_hidden_init_func=init.basic_init,
            net_last_init_func=init.uniform_init,
            activation_func=nn.ReLU,
            **kwargs):
        """
        Initialize the network.

        Args:
            self: (todo): write your description
            output_shape: (str): write your description
            base_type: (str): write your description
            append_hidden_shapes: (todo): write your description
            append_hidden_init_func: (todo): write your description
            init: (str): write your description
            basic_init: (str): write your description
            net_last_init_func: (todo): write your description
            init: (str): write your description
            uniform_init: (array): write your description
            activation_func: (todo): write your description
            nn: (todo): write your description
            ReLU: (todo): write your description
        """
        super().__init__()
        self.base = base_type(activation_func=activation_func, **kwargs)
        self.activation_func = activation_func
        append_input_shape = self.base.output_shape
        self.append_fcs = []
        for next_shape in append_hidden_shapes:
            fc = nn.Linear(append_input_shape, next_shape)
            append_hidden_init_func(fc)
            self.append_fcs.append(fc)
            self.append_fcs.append(self.activation_func())
            append_input_shape = next_shape

        self.last = nn.Linear(append_input_shape, output_shape)
        net_last_init_func(self.last)

        self.append_fcs.append(self.last)
        self.seq_append_fcs = nn.Sequential(*self.append_fcs)

    def forward(self, x):
        """
        Forward computation of x

        Args:
            self: (todo): write your description
            x: (todo): write your description
        """
        out = self.base(x)
        out = self.seq_append_fcs(out)
        return out


class FlattenNet(Net):
    def forward(self, input):
        """
        Forward computation.

        Args:
            self: (todo): write your description
            input: (todo): write your description
        """
        out = torch.cat(input, dim=-1)
        return super().forward(out)


class BootstrappedNet(nn.Module):
    def __init__(
            self,
            output_shape,
            base_type, head_num=10,
            append_hidden_shapes=[],
            append_hidden_init_func=init.basic_init,
            net_last_init_func=init.uniform_init,
            activation_func=nn.ReLU(),
            **kwargs):
        """
        Initialize the network.

        Args:
            self: (todo): write your description
            output_shape: (str): write your description
            base_type: (str): write your description
            head_num: (int): write your description
            append_hidden_shapes: (todo): write your description
            append_hidden_init_func: (todo): write your description
            init: (str): write your description
            basic_init: (str): write your description
            net_last_init_func: (todo): write your description
            init: (str): write your description
            uniform_init: (array): write your description
            activation_func: (todo): write your description
            nn: (todo): write your description
            ReLU: (todo): write your description
        """
        super().__init__()

        self.base = base_type(activation_func=activation_func, **kwargs)
        self.activation_func = activation_func

        self.bootstrapped_heads = []

        append_input_shape = self.base.output_shape

        for idx in range(head_num):
            append_input_shape = self.base.output_shape
            append_fcs = []
            for next_shape in append_hidden_shapes:
                fc = nn.Linear(append_input_shape, next_shape)
                append_hidden_init_func(fc)
                append_fcs.append(fc)
                # set attr for pytorch to track parameters( device )
                append_input_shape = next_shape

            last = nn.Linear(append_input_shape, output_shape)
            net_last_init_func(last)
            append_fcs.append(last)
            head = nn.Sequential(*append_fcs)
            self.__setattr__(
                "head{}".format(idx),
                head)
            self.bootstrapped_heads.append(head)

    def forward(self, x, head_idxs):
        """
        Parameters ---------- x : numpy array.

        Args:
            self: (todo): write your description
            x: (todo): write your description
            head_idxs: (str): write your description
        """
        output = []
        feature = self.base(x)
        for idx in head_idxs:
            output.append(self.bootstrapped_heads[idx](feature))
        return output


class FlattenBootstrappedNet(BootstrappedNet):
    def forward(self, input, head_idxs):
        """
        R forward computation.

        Args:
            self: (todo): write your description
            input: (todo): write your description
            head_idxs: (str): write your description
        """
        out = torch.cat(input, dim=-1)
        return super().forward(out, head_idxs)
