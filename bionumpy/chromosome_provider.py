import numpy as np
from itertools import groupby

class ChromosomeProvider:
    @staticmethod
    def get_chrom_name(char_array):
        return "".join(chr(c) for c in char_array).replace("\x00", "")
        
    @staticmethod
    def _is_same_chromosome(chrom_1, chrom_2):
        if chrom_1 is None:
            return False
        return FullBedFile.get_chrom_name(chrom_1) == FullBedFile.get_chrom_name(chrom_2)

    @staticmethod
    def _get_chromosome_changes(chromosomes):
        return np.flatnonzero(
            np.any(chromosomes[1:].__neq__(chromosomes[:-1]), axis=-1))+1

class ChromosomeStreamProvider(ChromosomeProvider):
    def __init__(self, file_buffers):
        self._buffers = file_buffers

    def __iter__(self):
        chrom_func = lambda b: self.get_chrom_name(b.chromosome[0])
        chrom_grouped = groupby(self._buffers, chrom_func)
        overlay = []
        for start_chrom, group in chrom_grouped:
            group = list(group)
            last_buffer = group[-1]
            chrom_changes = self._get_chromosome_changes(last_buffer.chromosome)
            if len(overlay) and self.get_chrom_name(overlay[0][0].chromosome) != start_chrom:
                yield self.get_chrom_name(overlay[0][0].chromosome), overlay[0]
                overlay = []
            if not chrom_changes.size:
                yield (start_chrom, np.concatenate(overlay + group))
                overlay = []
            else:
                print(chrom_changes[0])
                yield (start_chrom, np.concatenate(overlay + group[:-1] + [last_buffer[:chrom_changes[0]]]))
                overlay = [last_buffer[chrom_changes[-1]:]]
                if len(chrom_changes>1):
                    chunks = (last_buffer[start:end] for start, end in zip(chrom_changes[:-1], chrom_changes[1:]))
                    for chunk in chunks:
                        yield (self.get_chrom_name(chunk.chromosome[0]), chunk)
            last_chrom = last_buffer[-1].chromosome
        if len(overlay):
            chunk = overlay[0]
            yield (self.get_chrom_name(chunk.chromosome[0]), chunk)
# 
#         cur_data = []
#         last_chromosome = np.zeros(3, dtype=np.uint8)
#         last_chromosome = None
#         for file_buffer in self._buffers:
#             chromosomes = file_buffer.chromosome
#             if not len(chromosomes):
#                 break
#             if last_chromosome is not None and not self._is_same_chromosome(last_chromosome, chromosomes[0]) :
#                 yield (self.get_chrom_name(last_chromosome), np.concatenate(cur_data))
#                 last_chromosome = chromosomes[0]
#                 cur_data = []
#             data = file_buffer.data
#             chromosome_changes = self._get_chromosome_changes(chromosomes)
#             if len(chromosome_changes)==0:
#                 cur_data.append(data)
#                 continue
#             cur_data.append(data[:chromosome_changes[0]])
#             yield self.get_chrom_name(last_chromosome), np.concatenate(cur_intervals)
#             for start, end in zip(chromosome_changes[:-1], chromosome_changes[1:]):
#                 yield np.get_chrom_name(chromosomes[start]), data[start:end]
#             last_chromosome = chromosomes[-1]
#             cur_data.append(data[chromosome_changes[-1]:])
#         yield self.get_chrom_name(last_chromosome). np.concatenate(cur_data)

class ChromosomeDictProvider:
    pass
