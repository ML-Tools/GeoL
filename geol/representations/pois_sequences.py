"""
File description
"""

# Authors: Gianni Barlacchi <gianni.barlacchi@gmail.com>

import pandas as pd
import numpy as np
import gensim, logging
import matplotlib.pyplot as plt
from geol.utils import constants
from geol.geol_logger.geol_logger import logger
import pysal
import geopandas as gpd
from shapely.ops import nearest_points
from shapely.geometry import Point


class POISequences():

    def __init__(self, pois):

        self._pois = pois

    @classmethod
    def from_csv(cls, inputfile, sep='\t', crs=constants.default_crs):
        """
        Read csv file with POIs details, including latitude and longitude
        :param inputfile:
        :param sep:
        :return:
        """
        #  Read foursquare MAPPED onto the grid
        logger.info("Reading POIs dataset.")
        df = pd.read_csv(inputfile, sep=sep)

        # Create GeoDataFrame from the read DataFrame
        logger.info("Create GeoDataFrame")
        geometry = [Point(xy) for xy in zip(df.longitude, df.latitude)]
        gdf = gpd.GeoDataFrame(df, index=df.index, geometry=geometry, crs={'init': crs})

        return cls(gdf.to_crs({'init': constants.universal_crs}))

    def _centroid_distance(df):
        return df['geometry'].distance(df['centroid'])

    def _nearest(df):

        points = df[['categories', 'geometry']].copy()

        s = str(df.iloc[0]['categories']) + "\t"

        p = df.iloc[0]['geometry']
        points = points[points.geometry != p]

        while (len(points) > 0):
            nearest = points.geometry == nearest_points(p, points.geometry.unary_union)[1]
            # print points[nearest]['geometry'].iloc[0]
            p = points[nearest]['geometry'].iloc[0]

            s += str(points[nearest]['categories'].iloc[0]) + "\t"
            points = points[points['geometry'] != p]

        return s.strip()

    def _distance(self, band_size=500):

        wthresh = pysal.weights.DistanceBand.from_dataframe(self._pois, band_size, p=2, binary=False, ids=self._pois.index)

        ds = []

        for index, indexes in wthresh.neighbors.iteritems():

            if len(indexes) == 0:
                d = {}
                d['observation'] = index
                d['observed'] = index
                d['distance'] = None
                ds.append(d)
            else:
                for i in range(len(indexes)):
                    d = {}
                    d['observation'] = index
                    d['observed'] = indexes[i]
                    d['distance'] = wthresh.weights[index][i]
                    ds.append(d)

        return pd.DataFrame(ds)

    def distance_based_sequence(self, band_size, outfile):

        df = self._distance(band_size)

        df.sort_values(by=['observation', 'distance'], ascending=True, inplace=True)

        # Retrive observation/observed categories from the original dataframe
        tmp = df.merge(self._pois[['categories']], left_on='observed', right_index=True)\
            .merge(self._pois[['categories']], left_on='observation', right_index=True,
                   suffixes=['_observed', '_observation'])

        tmp = tmp.groupby(['observation', 'categories_observation']).apply(
            lambda x: '\t'.join(x['categories_observed'])).reset_index().rename(columns={0: "seq"})

        tmp.loc[:, "complete"] = tmp['categories_observation'] + "\t" + tmp['seq']

        tmp['complete'].to_csv(outfile, index=False, header=None)

    def nearest_based_sequence(self, outfile):

        df = self._pois.copy()

        df.loc[:, 'distance'] = df.apply(self._centroid_distance, axis=1)
        df.sort_values(by=['cellID', 'distance'], inplace=True, ascending=True)

        df.groupby('cellID').apply(self._nearest).to_csv(outfile, index=False, header=None)