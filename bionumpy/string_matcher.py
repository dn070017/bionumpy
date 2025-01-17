import logging

from bionumpy.rollable import RollableFunction
from bionumpy.sequences import as_encoded_sequence_array, create_sequence_array_from_already_encoded_data
import itertools
import numpy as np
import bionumpy as bnp
import re
from bionumpy.sequences import Sequence
from npstructures import RaggedArray


class StringMatcher(RollableFunction):
    def __init__(self, matching_sequence, encoding):
        self._encoding = encoding
        self._matching_sequence_array = as_encoded_sequence_array(matching_sequence, encoding=encoding)

    @property
    def window_size(self):
        return len(self._matching_sequence_array)

    def __call__(self, sequence):
        return np.all(sequence == self._matching_sequence_array, axis=-1)


class RegexMatcher(RollableFunction):
    """
    Matches regexes of various lengths across a RaggedArray of sequences by constructing a list of FixedLenRegexMatcher objects from the original
    flexible length regex expression.

    It overrides the rolling_window function from the superclass to invoke FixedLenRegexMatcher objects across different window sizes for matcher
    objects.
    """

    def __init__(self, matching_regex, encoding):
        self._sub_matchers = construct_flexible_len_regex_matchers(matching_regex, encoding)

    def __call__(self, sequence: Sequence):
        raise NotImplementedError

    @property
    def window_size(self):
        return [sub_matcher.window_size for sub_matcher in self._sub_matchers]

    def rolling_window(self, _sequence: RaggedArray, window_size: int = None, mode="valid"):
        if not isinstance(_sequence, np.ndarray):
            if hasattr(self, "_encoding") and self._encoding is not None:
                _sequence = as_encoded_sequence_array(_sequence, encoding=self._encoding)
            else:
                _sequence = RaggedArray(_sequence)

        if mode == "valid":
            logging.warning("Mode is set to 'valid' in rolling_window(), but RegexMatcher uses only mode 'same'. Switching to 'same'...")

        shape, sequence = (_sequence.shape, _sequence.ravel())
        out = np.zeros_like(_sequence, dtype=bool)

        for index, sub_matcher in enumerate(self._sub_matchers):
            windows = np.lib.stride_tricks.as_strided(sequence, strides=sequence.strides + sequence.strides,
                                                      shape=sequence.shape + (sub_matcher.window_size,), writeable=False)
            convoluted = sub_matcher(windows)
            if isinstance(_sequence, RaggedArray):
                out = np.logical_or(out, RaggedArray(convoluted, shape))
            elif isinstance(_sequence, np.ndarray):
                out = np.logical_or(out, np.lib.stride_tricks.as_strided(convoluted, shape))

        return out


class FixedLenRegexMatcher(RollableFunction):
    def __init__(self, matching_regex, encoding):
        self._sub_matchers = construct_fixed_len_regex_matchers(matching_regex, encoding)

    @property
    def window_size(self):
        return self._sub_matchers[0].window_size

    def __call__(self, sequence):
        union_of_sub_matches = self._sub_matchers[0](sequence)
        for matcher in self._sub_matchers:
            union_of_sub_matches = np.logical_or(union_of_sub_matches, matcher(sequence))
        return union_of_sub_matches


class MaskedStringMatcher(RollableFunction):
    def __init__(self, matching_sequence_array, mask):
        # assert isinstance(matching_sequence_array, Sequence), type(matching_sequence_array)
        assert isinstance(mask, np.ndarray)
        assert matching_sequence_array.shape == mask.shape
        self._matching_sequence_array = matching_sequence_array
        self._mask = mask

    @property
    def window_size(self):
        return len(self._matching_sequence_array)

    def __call__(self, sequence):
        assert sequence.shape[-1] == self.window_size, (sequence.shape, self._matching_sequence_array)
        direct_match = (sequence == self._matching_sequence_array)
        masked_or_match = np.logical_or(direct_match, self._mask)
        return np.all(masked_or_match, axis=-1)


def construct_fixed_len_regex_matchers(matching_regex: str, encoding):
    r = re.compile('\[[^\]]+\]')
    hit = r.search(matching_regex)
    if hit is None:
        return [construct_wildcard_matcher(matching_regex, encoding)]
    else:
        start, end = hit.span()
        pre, post = matching_regex[0: start], matching_regex[end:]
        return list(itertools.chain.from_iterable(
            [construct_fixed_len_regex_matchers(pre + symbol + post, encoding)
             for symbol in matching_regex[start + 1: end - 1]]))


def construct_flexible_len_regex_matchers(matching_regex: str, encoding):
    r = re.compile('(([A-Z]|\[[A-Z]+\])+)\.\{(\d*)\,(\d+)\}(.+)')
    hit = r.search(matching_regex)
    if hit is None:
        return construct_fixed_len_regex_matchers(matching_regex, encoding)
    else:

        min_gap = int(hit.group(3)) if hit.group(3) != '' else 0
        max_gap = int(hit.group(4))

        end_group_1 = hit.end(1)
        start_group_5 = hit.start(5)

        pre, post = matching_regex[0: end_group_1], matching_regex[start_group_5:]
        return list(itertools.chain.from_iterable(
            [construct_flexible_len_regex_matchers(pre + symbol + post, encoding)
             for symbol in [str("." * n) for n in range(min_gap, max_gap + 1)]]))


def construct_wildcard_matcher(matching_regex: str, encoding):
    mask = np.array([symbol == '.' for symbol in matching_regex])

    #assert encoding in (bnp.encodings.alphabet_encoding.ACTGArray,
    #                     bnp.encodings.alphabet_encoding.AminoAcidArray), f"NotImplemented: Support for other encodings {encoding} awaits a generic way to replace '.' with an arbitrary symbol supported by the encoding"
    replacement = encoding.encoding.decode(0) if hasattr(encoding, "encoding") else chr(encoding.decode(0))
    base_seq = as_encoded_sequence_array(matching_regex.replace('.', str(replacement)), encoding=encoding)

    return MaskedStringMatcher(base_seq, mask)
