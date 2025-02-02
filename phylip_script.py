import sys
import os
import gzip
import pandas as pd
from collections import defaultdict
from contextlib import redirect_stdout
from Bio import SeqIO
import re 
from ete3 import Tree

excluded_species =  ['tupChi1', 'speTri2', 'jacJac1', 'micOch1', 'criGri1', 'mesAur1', 'rn6', 'hetGla2', 'cavPor3', 'chiLan1', 'octDeg1', 'oryCun2', 'ochPri3', 'susScr3', 'vicPac2', 'camFer1', 'turTru2', 'orcOrc1', 'panHod1', 'bosTau8', 'oviAri3', 'capHir1', 'felCat8', 'musFur1', 'ailMel1', 'odoRosDiv1', 'lepWed1', 'pteAle1', 'pteVam1', 'eptFus1', 'myoDav1', 'myoLuc2', 'conCri1', 'loxAfr3', 'eleEdw1', 'triMan1', 'chrAsi1', 'echTel2', 'oryAfe1', 'dasNov3', 'monDom5', 'sarHar1', 'ornAna1', 'colLiv1', 'falChe1', 'falPer1', 'ficAlb2', 'zonAlb1', 'geoFor1', 'pseHum1', 'melUnd1', 'amaVit1', 'araMac1', 'anaPla1', 'galGal4', 'melGal1', 'allMis1', 'cheMyd1', 'chrPic2', 'anoCar2', 'tetNig2', 'gasAcu1', 'gadMor1', 'lepOcu1', 'cerSim1', 'macEug2', 'equCab2', 'eriEur2', 'sorAra2', 'oreNil2', 'oryLat2', 'taeGut2', 'latCha1', 'apaSpi1', 'pelSin1', 'fr3', 'neoBri1', 'hapBur1', 'mayZeb1', 'punNye1', 'danRer10', 'astMex1', 'xenTro7', 'xipMac1', 'takFla1', 'petMar2'] #["tupBel1", "mm10", "canFam3"] #hvorfor er disse eksluderet

species_dictionary=defaultdict(list)

def write_phylip(seqs, output_file):
    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))
    
    with open(output_file, "w") as dest, redirect_stdout(dest):
        lengths=[len(x) for x in seqs.values()]
        assert(all(lengths[0] == l for l in lengths))
        seq_length = lengths[0]

        for name in seqs:
            seqs[name]=seqs[name].replace("-", "?")
        
        print(f"{len(seqs)} {seq_length}")
        for name in sorted(seqs.keys(), key=lambda x: x!="hg38"):
            print(f"{name:<10}{seqs[name]}")

def write_fasta(seqs, output_file):
    if not os.path.exists(os.path.dirname(output_file)):
         os.makedirs(os.path.dirname(output_file))

    with open(output_file, "w") as dest, redirect_stdout(dest):
        lengths=[len(x) for x in seqs.values()]
        assert(all(lengths[0] == l for l in lengths))
        seq_length =lengths[0]

        for name in seqs:
            seqs[name]=seqs[name].replace("?", "-")
        
        for name in sorted(seqs.keys(), key=lambda x: x!="hg38"):
            print(f">{name}\n{seqs[name]}")

# command line arguments
_, fasta_file, id_table_file, tree_file, aln_stat_file, output_dir=sys.argv

# read id table
id_table = pd.read_csv(id_table_file, sep="\t").drop_duplicates("name2")
id_table["ucsc_gene_base"] = [x.rsplit(".", 1)[0] for x in id_table["name"]]
id_table.set_index("ucsc_gene_base", inplace=True)

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

skipped=0


# read tree
tree=Tree(tree_file, format=1)
# get all names of species in the tree
all_species = [t.name for t in tree.get_leaves()]
# unroot the tree (codeml uses unrooted trees)
tree.unroot()

# dictionary to keep track of which species are included in the produced alignment for the species
species_included = {}

# read fasta from gzipped (compressed file)
with gzip.open(fasta_file, "rt") as f:
    # keep track of what the last ucsc id we have seen is
    prev_ucsc_id = None

    #dictionary with lists as default values (for filling in the exons we read for each species)
    exons = defaultdict(list)

    #iterate over all the fasta entries in the fasta file (each entry is an exon of a cds)
    for entry in SeqIO.parse(f, "fasta"):
        #split the name attribute (fasta header line) to get info for the gene
        ucsc_id, assembly, exon_nr, exon_total = entry.name.split("_", 4)
        # if exon we are looking at belongs to the next gene, write the previous gene
        # and start with the next gene

        if prev_ucsc_id is not None and ucsc_id != prev_ucsc_id:
            try:
                # try to extract the ucsc gene name from the ucsc gene id
                name, version = prev_ucsc_id.rsplit(".", 1) #har ændret fra ucsc_id til prev_ucsc_id
                gene_name = id_table.loc[name, "geneName"]
                chrom = id_table.loc[name, "#chrom"]

                is_coding = id_table.loc[name, "transcriptClass"] == "coding" and "pseudo" not in id_table.loc[name, "transcriptType"]

            except KeyError:
                # if that is not possible, we skip the gene
                skipped +=1
            
            else:
                # if it was possible, we go on
                print(gene_name)

                #make a dictionary with the concatenated exons (CDS) for each gene
                cds_alignment={}

                for species in exons:
                    if species not in excluded_species:
                        cds_alignment[species]="".join(exons[species]).upper()

                # # regular expression for selecting only those with an aligned start and stop codon no inframe stop codons:
                regex1 = re.compile(r"ATG(?:(?!TAA|TAG|TGA)...)*(?:TAA|TAG|TGA)$")
                regex2 = re.compile(r"ATG(?:(?![A-Z]--|--[A-Z]|-[A-Z]-|[A-Z]-[A-Z]|-[A-Z][A-Z]|[A-Z][A-Z]-)...)*(?:TAA|TAG|TGA)$")
                
                # # regular expression for truncating at inframe stop codons:
                # regex = re.compile(r"(?:(?!TAA|TAG|TGA)...)*(?:TAA|TAG|TGA)")
                
                # use the regular expression on each sequence 
                for species in list(cds_alignment.keys()):
                    match1 = regex1.match(cds_alignment[species])
                    match2 = regex2.match(cds_alignment[species])

                    if match1 and match2:
                        # remove the stop codon found
                        start, end = match2.span()
                        cds_alignment[species] = cds_alignment[species][:end-3]+"?"*(len(cds_alignment[species])-end+3)
                    else:
                        # delete the species and their sequences if the regular expression does not match
                        del cds_alignment[species]
                
                # keep the alignments with human and at least two other species
                if is_coding and "hg38" in cds_alignment and len(cds_alignment) >=2:
                    # record which species are in the alignment
                    species_included[gene_name] = list(cds_alignment.keys())

                    # write phylip file
                    output_path = os.path.join(output_dir, chrom, gene_name, gene_name + ".phylip")
                    write_phylip(cds_alignment, output_path)

                    # write fasta file (in case ypu need it)
                    output_path = os.path.join(output_dir, chrom, gene_name, gene_name + ".fa")
                    write_fasta(cds_alignment, output_path)

                    # write species dict
                    species_dictionary[chrom].append(gene_name)

                    # remove the species from the tree that were removed from the alignment
                    alignment_tree = tree.copy("newick")
                    alignment_tree.prune(list(cds_alignment.keys())) #denne her linje fejler

                    #write the tree for the alignment
                    output_path = os.path.join(output_dir, chrom, gene_name, gene_name + ".nw")
                    alignment_tree.write(format=1, outfile=output_path)

                else:
                    skipped += 1
                
                # empty the exon dictionary
                exons = defaultdict(list)

        # add an exon sequence to the list for the species (assembly e.g. hg38)
        exons[assembly].append(str(entry.seq))                               

        # make our current id the precious one
        prev_ucsc_id = ucsc_id


    try:
        # try to extract the ucsc gene name from the ucsc gene id
        name, version = prev_ucsc_id.rsplit(".", 1) #har ændret fra ucsc_id til prev_ucsc_id
        gene_name = id_table.loc[name, "geneName"]
        chrom = id_table.loc[name, "#chrom"]
        is_coding = id_table.loc[name, "transcriptClass"] == "coding" and "pseudo" not in id_table.loc[name, "transcriptType"]

    except KeyError:
        # if that is not possible, we skip the gene
        skipped +=1
            
    else:
        # if it was possible, we go on
        print(gene_name)

        #make a dictionary with the concatenated exons (CDS) for each gene
        cds_alignment={}
        for species in exons:
            if species not in excluded_species:
                cds_alignment[species]="".join(exons[species]).upper()
                
                # # regular expression for selecting only those with an aligned start and stop codon no inframe stop codons:
                regex1 = re.compile(r"ATG(?:(?!TAA|TAG|TGA)...)*(?:TAA|TAG|TGA)$")
                regex2 = re.compile(r"ATG(?:(?![A-Z]--|--[A-Z]|-[A-Z]-|[A-Z]-[A-Z]|-[A-Z][A-Z]|[A-Z][A-Z]-)...)*(?:TAA|TAG|TGA)$")

                # # regular expression for truncating at inframe stop codons:
                # regex = re.compile(r"(?:(?!TAA|TAG|TGA)...)*(?:TAA|TAG|TGA)")
                
                # use the regular expression on each sequence 
        for species in list(cds_alignment.keys()):
            match1 = regex1.match(cds_alignment[species])
            match2 = regex2.match(cds_alignment[species])
            
            if match1 and match2:
                # remove the stop codon found
                start, end = match2.span()
                cds_alignment[species] = cds_alignment[species][:end-3]+"?"*(len(cds_alignment[species])-end+3)

            else:
                # delete the species and their sequences if the regular expression does not match
                del cds_alignment[species]
                
        # keep the alignments with human and at least two other species
        if is_coding and "hg38" in cds_alignment and len(cds_alignment) >=2:
            # record which species are in the alignment
            species_included[gene_name] = list(cds_alignment.keys())

            # write phylip file
            output_path = os.path.join(output_dir, chrom, gene_name, gene_name + ".phylip")
            write_phylip(cds_alignment, output_path)

            # write fasta file (in case ypu need it)
            output_path = os.path.join(output_dir, chrom, gene_name, gene_name + ".fa")
            write_fasta(cds_alignment, output_path)

            # write species dict
            species_dictionary[chrom].append(gene_name)

            # remove the species from the tree that were removed from the alignment
            alignment_tree = tree.copy("newick")
            alignment_tree.prune(list(cds_alignment.keys())) #denne her linje fejler

            #write the tree for the alignment
            output_path = os.path.join(output_dir, chrom, gene_name, gene_name + ".nw")
            alignment_tree.write(format=1, outfile=output_path)


                
print(f"Skipped {skipped} genes")
print(species_dictionary)

records = []
for gene, aligned_species in species_included.items():
    row = [gene] + [species in aligned_species for species in all_species]
    records.append(row)
df = pd.DataFrame().from_records(records, columns=["gene"] + all_species)
df.to_csv(aln_stat_file, index=False)

