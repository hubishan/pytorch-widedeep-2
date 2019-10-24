import numpy as np
import torch

from torch import nn
from ..wdtypes import *


def dense_layer(inp:int, out:int, dropout:float, batchnorm=False):
    if batchnorm:
        return nn.Sequential(
            nn.Linear(inp, out),
            nn.BatchNorm1d(out),
            nn.LeakyReLU(inplace=True),
            nn.Dropout(dropout)
            )
    else:
        return nn.Sequential(
            nn.Linear(inp, out),
            nn.LeakyReLU(inplace=True),
            nn.Dropout(dropout)
            )


class DeepDense(nn.Module):
    r"""Dense branch of the deep side of the model. This class combines embedding
    representations of the categorical features with numerical (aka
    continuous) features. These are then passed through a series of dense
    layers.

    Parameters
    ----------
    deep_column_idx: Dict containing the index of the columns that will be
        passed through the DeepDense model. Required to slice the tensors. e.g.
        {'education': 0, 'relationship': 1, 'workclass': 2, ...}
    hidden_layers: List with the number of neurons per dense layer. e.g: [64,32]
    dropout: Optional List with the dropout between the dense layers.
        e.g: [0.5,0.5]
    batchnorm: Optional Boolean indicating whether or not to include batch
        normalizatin in the dense layers
    embeddings_input: Optional List of Tuples with the column name, number of
        unique values and embedding dimension. e.g. [(education, 11, 32), ...]
    continuous_cols: Optional List with the name of the numeric (aka
        continuous) columns

    **Either embeddings_input or continuous_cols (or both) should be passed to the
    model

    Attributes
    ----------
    dense: nn.Sequential model of dense layers that will receive the
        concatenation of the  embeddings and the continuous columns
    embed_layers: nn.ModuleDict with the embedding layers
    output_dim: integer containing the output dimension of the model. This is a
        required attribute neccesary to build the WideDeep class

    Example
    --------
    >>> import torch
    >>> from pytorch_widedeep.models import DeepDense
    >>> X_deep = torch.cat((torch.empty(5, 4).random_(4), torch.rand(5, 1)), axis=1)
    >>> colnames = ['a', 'b', 'c', 'd', 'e']
    >>> embed_input = [(u,i,j) for u,i,j in zip(colnames[:4], [4]*4, [8]*4)]
    >>> deep_column_idx = {k:v for v,k in enumerate(colnames)}
    >>> model = DeepDense(hidden_layers=[8,4], deep_column_idx=deep_column_idx, embed_input=embed_input)
    >>> model(X_deep)
    tensor([[ 3.4470e-02, -2.0089e-03,  4.7983e-02,  3.3500e-01],
            [ 1.4329e-02, -1.3800e-03, -3.3617e-04,  4.1046e-01],
            [-3.3546e-04,  3.2413e-02, -4.1198e-03,  4.8717e-01],
            [-6.7882e-04,  7.9103e-03, -1.9960e-03,  4.2134e-01],
            [ 6.7187e-02, -1.2821e-03, -3.0960e-04,  3.6123e-01]],
           grad_fn=<LeakyReluBackward1>)
    """
    def __init__(self,
        deep_column_idx:Dict[str,int],
        hidden_layers:List[int],
        dropout:Optional[List[float]]=None,
        batchnorm:Optional[bool]=None,
        embed_input:Optional[List[Tuple[str,int,int]]]=None,
        continuous_cols:Optional[List[str]]=None):

        super(DeepDense, self).__init__()
        self.embed_input = embed_input
        self.continuous_cols = continuous_cols
        self.deep_column_idx = deep_column_idx

        # Embeddings
        if self.embed_input is not None:
            self.embed_layers = nn.ModuleDict({'emb_layer_'+col: nn.Embedding(val, dim)
                for col, val, dim in self.embed_input})
            emb_inp_dim = np.sum([embed[2] for embed in self.embed_input])
        else:
            emb_inp_dim = 0

        # Continuous
        if self.continuous_cols is not None: cont_inp_dim = len(self.continuous_cols)
        else: cont_inp_dim = 0

        # Dense Layers
        input_dim = emb_inp_dim + cont_inp_dim
        hidden_layers = [input_dim] + hidden_layers
        if not dropout: dropout = [0.]*len(hidden_layers)
        batchnorm = batchnorm if batchnorm is not None else False
        self.dense = nn.Sequential()
        for i in range(1, len(hidden_layers)):
            self.dense.add_module(
                'dense_layer_{}'.format(i-1),
                dense_layer( hidden_layers[i-1], hidden_layers[i], dropout[i-1], batchnorm))

        # the output_dim attribute will be used as input_dim when "merging" the models
        self.output_dim = hidden_layers[-1]

    def forward(self, X:Tensor)->Tensor:
        if self.embed_input is not None:
            embed = [self.embed_layers['emb_layer_'+col](X[:,self.deep_column_idx[col]].long())
                for col,_,_ in self.embed_input]
        if self.continuous_cols is not None:
            cont_idx = [self.deep_column_idx[col] for col in self.continuous_cols]
            cont = X[:, cont_idx].float()
        try:
            out = self.dense(torch.cat(embed+[cont], 1))
        except:
            try:
                out = self.dense(torch.cat(embed, 1))
            except:
                out = self.dense(cont)
        return out
