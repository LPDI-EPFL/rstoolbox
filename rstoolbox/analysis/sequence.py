# @Author: Jaume Bonet <bonet>
# @Date:   10-Oct-2017
# @Email:  jaume.bonet@gmail.com
# @Filename: sequence.py
# @Last modified by:   bonet
# @Last modified time: 14-Mar-2018

import copy
import collections

import pandas as pd
import numpy as np

from SimilarityMatrix import SimilarityMatrix as SM


def _get_sequential_table( seqType ):
    """
    Generates the table to fill sequence data in order to create
    a :py:class:`.SequenceFrame`

    :param seqType: Type of sequence: protein, protein_sse, dna, rna.
    :type seqType: :py:class:`str`
    :return: dict
    :raise ValueError: If seqType is not known
    """
    table = {}
    extra = []
    if seqType.lower() == "protein":
        # X = UNKNOWN  # * = GAP
        # B = N or D   # Z = E or Q
        table = {
            'C': [], 'D': [], 'S': [], 'Q': [], 'K': [],
            'I': [], 'P': [], 'T': [], 'F': [], 'N': [],
            'G': [], 'H': [], 'L': [], 'R': [], 'W': [],
            'A': [], 'V': [], 'E': [], 'Y': [], 'M': [],
            'X': [], '*': [], 'B': [], 'Z': []
        }
        extra = ['X', '*', 'B', 'Z']
    elif seqType.lower() in ["dna", "rna"]:
        # B = C or G or T  # D = A or G or T
        # H = A or C or T  # K = G or T
        # M = A or C       # N = A or C or G or T
        # R = A or G       # S = C or G
        # V = A or C or G  # W = A or T
        # Y = C or T
        table = {
            'C': [], 'A': [], 'T': [], 'G': [], 'X': [], '*': [],
            'B': [], 'D': [], 'H': [], 'K': [], 'M': [], 'N': [],
            'R': [], 'S': [], 'V': [], 'W': [], 'Y': []
        }
        if seqType.lower() == "rna":
            table.setdefault( 'U', [])
            table.pop('T', None)
        extra = ['X', '*', 'B', 'D', 'H', 'K', 'M', 'N', 'R', 'S', 'V', 'W', 'Y']
    elif seqType.lower == "protein_sse":
        table = {
            'H': [], 'E': [], 'L': [], '*': [], 'G': []
        }
        extra = ['*', 'G']
    else:
        raise ValueError("sequence type {0} unknown".format(seqType))
    return table, extra


def _sequence_similarity( qseq, rseq, matrix ):
    assert len(qseq) == len(rseq)
    raw, idn, pos, neg = 0, 0, 0, 0
    ali = []
    for i in range(len(qseq)):
        sc = matrix.get_value(qseq[i], rseq[i])
        raw += sc
        if qseq[i] == rseq[i]:
            idn += 1
            pos += 1
            ali.append(rseq[i])
        elif sc > 0:
            pos += 1
            ali.append("+")
        else:
            neg += 1
            ali.append(".")
    return raw, idn, pos, neg, "".join(ali)


def _positional_similarity( qseq, rseq, matrix ):
    raw, idn, pos, neg = 0, 0, 0, 0
    for i in range(len(qseq)):
        sc = matrix.get_value(qseq[i], rseq)
        raw += sc
        if qseq[i] == rseq:
            idn += 1
        if sc > 0:
            pos += 1
        else:
            neg += 1
    return raw, idn, pos, neg


def sequential_frequencies( self, seqID, qType="sequence", seqType="protein",
                            cleanExtra=True, cleanUnused=-1 ):
    """
    Generates a :py:class:`.SequenceFrame` for the frequencies of
    the sequences in the :py:class:`.DesignFrame` with seqID identifier.
    If there is a reference_sequence for this seqID, it will also
    be attached to the :py:class:`.SequenceFrame`.
    All letters in the sequence will be capitalized. All symbols that
    do not belong to string.ascii_uppercase will be transformed to "*"
    as this is the symbol recognized by the substitution matrices.

    :param str seqID: Identifier of the sequence sets of interest.
    :param str seqType: Type of sequence: protein, protein_sse, dna, rna.
    :param bool cleanExtra: Remove from the SequenceFrame the non-regular
        amino/nucleic acids if they are empty for all positions.
    :param int cleanUnused: Remove from the SequenceFrame the regular
        amino/nucleic acids if they frequency is equal or under the value . Default is -1,
        so nothing is deleted.
    :return: :py:class:`.SequenceFrame`
    """
    from rstoolbox.components import SequenceFrame

    def count_instances( seq, table ):
        t = copy.deepcopy(table)
        c = collections.Counter(seq)
        for aa in table:
            _ = c[aa]
            if _ > 0:
                t[aa] = float(_) / len(seq)
            else:
                t[aa] = 0
        return t

    sserie = self.get_sequential_data(qType, seqID).replace('', np.nan).dropna().str.upper()
    table, extra = _get_sequential_table( seqType )
    sserie = sserie.apply(lambda x: pd.Series(list(x)))
    sserie = sserie.apply(lambda x: pd.Series(count_instances(x.str.cat(), table))).T

    df = SequenceFrame(sserie)
    df.measure("frequency")
    df.extras( extra )
    if self.has_reference_sequence(seqID):
        df.reference_sequence(
            self.get_reference_sequence(seqID),
            self.get_reference_shift(seqID))
    df.delete_extra( cleanExtra )
    df.delete_empty( cleanUnused )
    df.clean()
    df.index = df.index + self.get_reference_shift(seqID)
    return df


def sequence_similarity( df, seqID, key_residues=None, matrix="BLOSUM62" ):
    """
    Evaluate the sequence similarity between each decoy and the reference sequence
    for a given seqID.
    Will create several new columns:

    ===============================  ===================================================
    New Column                       Data Content
    ===============================  ===================================================
    **<matrix>_<seqID>_score_raw**   Score obtained by applying `<matrix>`
    **<matrix>_<seqID>_score_perc**  Score obtained by applying `<matrix>` over score \
                                     of reference_sequence against itself
    **<matrix>_<seqID>_identity**    Total identity matches
    **<matrix>_<seqID>_positive**    Total positive matches according to `<matrix>`
    **<matrix>_<seqID>_negative**    Notal negative matches according to `<matrix>`
    **<matrix>_<seqID>_ali**         Representation of aligned residues
    ===============================  ===================================================


    Running this function multiple times (different key_residue selections, for example)
    adds suffix to the previously mentioned columns following pandas' merge naming
    logic (_x, _y, _z, ...).

    :param df: designs data.
    :type df: :py:class:`.DesignFrame`
    :param seqID: Identifier of the sequence sets of interest.
    :type seqID: :py:class:`str`
    :param matrix: Identifier of the matrix used to evaluate similarity. Default is BLOSUM62.
    :type matrix: :py:class:`str`

    :return: :py:class:`.DesignFrame`.

    :raises:
        :AttributeError: if the data passed is not a :py:class:`.DesignFrame`.
        :KeyError: if ``seqID`` cannot be found.
        :AttributeError: if there is no reference for ``seqID``.
    """
    from rstoolbox.components import DesignFrame

    if not isinstance(df, DesignFrame):
        raise AttributeError("Input data has to be a DesignFrame with a reference sequence.")
    if not df.has_reference_sequence(seqID):
        raise AttributeError("There is no reference sequence for seqID {}".format(seqID))
    if not "sequence_{}".format(seqID) in df:
        raise KeyError("Sequence {} not found in decoys.".format(seqID))

    mat = SM.get_matrix(matrix)
    ref_seq = df.get_reference_sequence(seqID, key_residues)
    ref_raw, ref_id, ref_pos, ref_neg, ali = _sequence_similarity(ref_seq, ref_seq, mat)
    df2 = df._constructor(df.get_sequence(seqID, key_residues))
    df2 = df2.apply(
        lambda x: pd.Series(_sequence_similarity(x.get_sequence(seqID), ref_seq, mat)), axis=1)
    df2[5] = df2[0] / ref_raw
    df2 = df2.rename(pd.Series(["{0}_{1}_raw".format(matrix.lower(), seqID),
                                "{0}_{1}_identity".format(matrix.lower(), seqID),
                                "{0}_{1}_positive".format(matrix.lower(), seqID),
                                "{0}_{1}_negative".format(matrix.lower(), seqID),
                                "{0}_{1}_ali".format(matrix.lower(), seqID),
                                "{0}_{1}_perc".format(matrix.lower(), seqID)]),
                     axis="columns").rename(pd.Series(df.index.values), axis="rows")
    return pd.concat([df.reset_index(drop=True),
                      df2.reset_index(drop=True)], axis=1)


def positional_sequence_similarity( df, seqID=None, ref_seq=None, matrix="BLOSUM62" ):
    """
    Generates per-position match data of the provided sequence over the reference sequence.

    :param df: Input data.
    :type df: Union[:py:class:`.DesignFrame`, :py:class:`.FragmentFrame`]
    :param seqID: Identifier of the sequence sets of interest.
    Required when input is :py:class:`.DesignFrame`
    :type seqID: :py:class:`str`
    :param ref_seq: Reference sequence. Required when input is :py:class:`.FragmentFrame`.
    Will overwrite the reference sequence of :py:class:`.DesignFrame` if provided.
    :type ref_seq: :py:class:`str`
    :param matrix: Identifier of the matrix used to evaluate similarity. Default is BLOSUM62.
    :type matrix: :py:class:`str`

    :return: :py:class:`~pandas.DataFrame` where rows are positions and
    columns are `identity_perc` and `positive_perc`.

    :raises:
        :AttributeError: if the data passed is not in
        Union[:py:class:`.DesignFrame`, :py:class:`.FragmentFrame`].
        :AttributeError: if input is :py:class:`.DesignFrame` and ``seqID`` is not provided.
        :KeyError: if input is :py:class:`.DesignFrame` and ``seqID`` cannot be found.
        :AttributeError: if input is :py:class:`.DesignFrame` and there is no reference
        for ``seqID``.
        :AttributeError if input is :py:class:`.FragmentFrame` and ``ref_seq`` is not provided.
    """
    from rstoolbox.components import DesignFrame, FragmentFrame
    data = {"identity_perc": [], "positive_perc": []}
    mat = SM.get_matrix(matrix)

    # @todo: Code positional_sequence_similarity for DesignFrame
    # @body: Should behave the same way it does for the FragmentFrame
    if isinstance(df, DesignFrame):
        if seqID is None:
            raise AttributeError("seqID needs to be provided")
        if not df.has_reference_sequence(seqID):
            raise AttributeError("There is no reference sequence for seqID {}".format(seqID))
        if not "sequence_{}".format(seqID) in df:
            raise KeyError("Sequence {} not found in decoys.".format(seqID))

        ref_seq = ref_seq if ref_seq is not None else df.get_reference_sequence(seqID)
        seqdata = df.get_sequence(seqID)
        seqdata = seqdata.apply(lambda x: pd.Series(list(x)))
        for _, i in enumerate(seqdata.columns.values):
            qseq = "".join(seqdata[i].tolist())
            raw, idn, pos, neg = _positional_similarity( qseq, ref_seq[_], mat )
            data["identity_perc"].append(float(idn) / float(len(qseq)))
            data["positive_perc"].append(float(pos) / float(len(qseq)))

    elif isinstance(df, FragmentFrame):
        if ref_seq is None:
            raise AttributeError("ref_seq needs to be provided")

        for i in df["position"].drop_duplicates().values:
            qseq = "".join(df[df["position"] == i]["aa"].values)
            raw, idn, pos, neg = _positional_similarity( qseq, ref_seq[i - 1], mat )
            data["identity_perc"].append(float(idn) / float(len(qseq)))
            data["positive_perc"].append(float(pos) / float(len(qseq)))

    else:
        raise AttributeError("Input data has to be a DesignFrame with a "
                             "reference sequence or a FragmentFrame.")

    dfo = pd.DataFrame(data)
    dfo.index = dfo.index + 1
    return dfo
# old


def _extract_key_residue_sequence( seq, key_residues=None ):
    if key_residues is None:
        return seq
    tmp_seq = ""
    for k in key_residues:
        tmp_seq += seq[k-1]
    return tmp_seq


def _pick_key_residues( seq, key_residues=None ):
    if key_residues is None:
        return seq
    tmp_seq = ""
    for k in key_residues:
        tmp_seq += seq[k]
    return tmp_seq


def _calculate_linear_sequence_similarity( qseq, rseq, matrix, key_residues=None ):
    score = 0;
    qseq = _extract_key_residue_sequence( qseq, key_residues )
    rseq = _extract_key_residue_sequence( rseq, key_residues )
    assert len(qseq) == len(rseq)
    for i in range(len(qseq)):
        score += matrix.get_value(qseq[i], rseq[i])
    return score



def _calculate_binary_sequence_similarity( qseq, rseq, matrix, key_residues=None ):
    new_seq = ""
    qseq = _extract_key_residue_sequence( qseq, key_residues )
    rseq = _extract_key_residue_sequence( rseq, key_residues )
    assert len(qseq) == len(rseq)
    for i in range(len(qseq)):
        if matrix.get_value(qseq[i], rseq[i]) >= 1:
            new_seq += "1"
        else:
            new_seq += "0"
    return new_seq


def pick_key_residues( df, seqID, key_residues=None ):
    """
    Select the residues of interest from sequence seqID.

    :param df: designs data.
    :type df: :py:class:`.DesignFrame`
    :param seqID: Identifier of the sequence sets of interest.
    :type seqID: :py:class:`str`
    :param key_residues: Residues of interest. Are affected by the reference shift (if any).
    One can provide a list of residues to work with or a string indicating a LABEL to use.
    :type key_residues: Union[:py:class:`list`[:py:class:`int`], :py:class:`str`]

    :return: :py:class:`~pandas.DataFrame` with a single column named `sequence_[seqID]`.

    :raises:
        :AttributeError: if the data passed is not a :py:class:`.DesignFrame`.
        :KeyError: if ``seqID`` cannot be found.
        :KeyError: if a label is requested and not found .
    """
    from rstoolbox.components import DesignFrame
    if not isinstance(df, DesignFrame):
        raise AttributeError("Input data has to be a DesignFrame with a reference sequence.")
    if not "sequence_{}".format(seqID) in df:
        raise KeyError("Sequence {} not found in decoys.".format(seqID))


    if key_residues is None:
        return pd.DataFrame(df["sequence_{}".format(seqID)])

    # @todo: Implement label-based residue selection in pick_key_residues
    # @body: This will allow auto-selection from labels generated in RosettaScript
    elif isinstance( key_residues, str ):
        pass

    selected_residues = np.array(key_residues) - df.get_reference_shift(seqID)

    if np.any(selected_residues < 0):
        raise IndexError("Selected residue out of specified bound")
    if np.any(selected_residues > len(df["sequence_{}".format(seqID)].values[0]) + df.get_reference_shift(seqID) - 1):
        raise IndexError("Selected residue out of specified bound")

    sr = df.apply(lambda x : _pick_key_residues(x["sequence_{}".format(seqID)], selected_residues), axis=1)
    return pd.DataFrame(sr).rename({0:"sequence_{}".format(seqID)}, axis="columns")







def binary_similarity( df, ref_seq, matrix="IDENTITY", seq_column="sequence", prefix=None, key_residues=None ):
    mat       = SM.get_matrix(matrix)
    all_seqs  = df[[seq_column]]
    sims      = []
    if prefix is None:
        prefix = matrix.lower()
    else:
        prefix = str(prefix) + matrix.lower()
    for v in all_seqs.values:
        sims.append( _calculate_binary_sequence_similarity( v[0], ref_seq, mat, key_residues ) )
    wdf = df.copy()
    if prefix + "_binary" in df:
        wdf = wdf.drop([prefix + "_binary"], axis=1)
    wdf.insert( wdf.shape[1], prefix + "_binary", pd.Series( sims, index=wdf.index ) )
    return wdf

def binary_overlap( df, column_name="identity_binary" ):
    a = df[column_name].values
    x = len(a[0])
    result = [0] * x
    for seq in a:
        for _, b in enumerate(seq):
            if bool(int(b)): result[_] = 1
    return result

# def sequence_frequency_matrix( series, seq_column="sequence" ):
#     sserie = series[seq_column].values
#     table = {
#         'C' : [], 'D' : [], 'S' : [], 'Q' : [], 'K' : [],
#         'I' : [], 'P' : [], 'T' : [], 'F' : [], 'N' : [],
#         'G' : [], 'H' : [], 'L' : [], 'R' : [], 'W' : [],
#         'A' : [], 'V' : [], 'E' : [], 'Y' : [], 'M' : []
#     }
#
#     for x in range(len(sserie[0])):
#         for k in table:
#             table[k].append(float(0))
#         for y in range(len(sserie)):
#             aa = sserie[y][x]
#             table[aa][-1] += float(1)
#     for k in table:
#         for x in range(len(table[k])):
#             if table[k][x] != 0:
#                 table[k][x] /= float(len(sserie))
#
#     df = pd.DataFrame( table )
#     df.index = df.index + 1
#     return df
