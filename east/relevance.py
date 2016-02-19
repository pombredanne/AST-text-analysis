# -*- coding: utf-8 -*

from collections import defaultdict
import math

from east.asts import base
from east import consts
from east import utils


class RelevanceMeasure(object):

    def set_text_collection(self, texts):
        raise NotImplemented()

    def relevance(self, keyphrase, text, synonimizer=None):
        # text is the index of the text to measure the relevance to
        # TODO(mikhaildubov): Add detailed docstrings
        raise NotImplemented()


class ASTRelevanceMeasure(RelevanceMeasure):

    def __init__(self, ast_algorithm=consts.ASTAlgorithm.EASA, normalized=True):
        super(ASTRelevanceMeasure, self).__init__()
        self.ast_algorithm = ast_algorithm
        self.normalized = normalized

    def set_text_collection(self, texts):
        self.texts = texts
        self.asts = [base.AST.get_ast(utils.text_to_strings_collection(text), self.ast_algorithm)
                     for text in texts]

    def relevance(self, keyphrase, text, synonimizer=None):
        return self.asts[text].score(keyphrase, normalized=self.normalized,
                                     synonimizer=synonimizer)


class CosineRelevanceMeasure(RelevanceMeasure):

    def __init__(self, vector_space=consts.VectorSpace.STEMS,
                 term_weighting=consts.TermWeighting.TF_IDF):
        super(CosineRelevanceMeasure, self).__init__()
        self.vector_space = vector_space
        self.term_weighting = term_weighting
        

    def set_text_collection(self, texts):
        raw_tokens = [utils.tokenize_and_filter(utils.prepare_text(text)) for text in texts]
        # Convert to stems or lemmata, depending on the vector space type
        preprocessed_tokens = self._preprocess_tokens(raw_tokens)
        # Terms define the vector space (they can be words, stems or lemmata). They should be
        # defined once here because they will be reused when we compute td-idf for queries
        self.terms = list(set(utils.flatten(preprocessed_tokens)))
        self.tf, self.idf = self._tf_idf(preprocessed_tokens)


    def _preprocess_tokens(self, tokens):
        if self.vector_space == consts.VectorSpace.WORDS:
            return tokens
        if self.vector_space == consts.VectorSpace.STEMS:
            # TODO(mikhaildubov): Consider using SnowballStemmer + auto language detection
            from nltk.stem import porter
            stemmer = porter.PorterStemmer()
            return [[stemmer.stem(token) for token in tokens[i]] for i in xrange(len(tokens))]
        elif self.vector_space == consts.VectorSpace.LEMMATA:
            # TODO(mikhaildubov): Implement this (what lemmatizer to use here?)
            raise NotImplemented()


    def _tf_idf(self, tokens):
        # Calculate the inverted term index to facilitate further calculations
        term_index = {}
        for i in xrange(len(self.terms)):
            term_index[self.terms[i]] = i

        text_collection_size = len(tokens)

        # Calculate TF and IDF
        tf = [[0] * len(self.terms) for _ in xrange(text_collection_size)]
        idf_docs = defaultdict(set)
        for i in xrange(text_collection_size):
            for token in tokens[i]:
                if token in term_index:
                    tf[i][term_index[token]] += 1
                    idf_docs[token].add(i)
            # TF Normalization
            tf[i] = [freq * 1.0 / max(len(tokens[i]), 1) for freq in tf[i]]
        # Actual IDF metric calculation
        idf = [0] * len(self.terms)
        for term in idf_docs:
            idf[term_index[term]] = 1 + math.log(text_collection_size * 1.0 / len(idf_docs[term]))

        return tf, idf


    def _cosine_similarity(self, u, v):
        import numpy as np

        u_norm = math.sqrt(np.dot(u, u)) if np.count_nonzero(u) else 1.0
        v_norm = math.sqrt(np.dot(v, v)) if np.count_nonzero(v) else 1.0
        return np.dot(u, v) / (u_norm * v_norm)


    def relevance(self, keyphrase, text, synonimizer=None):
        # Based on: https://janav.wordpress.com/2013/10/27/tf-idf-and-cosine-similarity/,
        # but query vectors are defined here in the same vector space as document vectors
        # (not in the reduced one as in the article).
        import numpy as np

        # TF-IDF for query tokens
        query_tokens = self._preprocess_tokens(
                                        [utils.tokenize_and_filter(utils.prepare_text(keyphrase))])
        query_tf, query_idf = self._tf_idf(query_tokens)
        query_tf = query_tf[0]

        # Weighting for both text and query (either TF or TF-IDF)
        if self.term_weighting == consts.TermWeighting.TF:
            text_vector = self.tf[text]
            query_vector = query_tf
        elif self.term_weighting == consts.TermWeighting.TF_IDF:
            text_vector = np.multiply(self.tf[text], self.idf)
            query_vector = np.multiply(query_tf, query_idf)

        return self._cosine_similarity(text_vector, query_vector)
