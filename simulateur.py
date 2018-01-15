#! /usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np
import pandas as pd
import json
import sys
import openfisca_core
from openfisca_france import FranceTaxBenefitSystem
from openfisca_france.reforms import plf2018

class Simulator():
    def __init__(self):
        self.tax_benefit_system = FranceTaxBenefitSystem()
        self.reform = plf2018.plf2018(self.tax_benefit_system)
        self.period = 'year:2016:7'
        self.period_range = range(2018, 2023)

    def run(self, profile):
        profile = self.__format_profile(profile)
        reform_simulation = self.__init_profile(self.reform.new_scenario(), profile).new_simulation()
        reference_simulation = self.__init_profile(self.tax_benefit_system.new_scenario(), profile).new_simulation()
        return self.__launch_simulation(reference_simulation, reform_simulation)

    def __format_profile(self, profile):
        profile['period'] = self.period
        profile['enfants'] = [{'age': 9} for _ in range(0, profile['enfants'])]
        for key in ['parent1', 'parent2']:
            if key in profile:
                if 'salaire_de_base' in profile[key]:
                    profile[key]['salaire_de_base'] = profile[key]['salaire_de_base']*12*7
                if 'retraite_brute' in profile[key]:
                    profile[key]['retraite_brute'] = profile[key]['retraite_brute']*12*7
                if 'chomage_brut' in profile[key]:
                    profile[key]['chomage_brut'] = profile[key]['chomage_brut']*12*7
        if 'menage' in profile:
            if 'loyer' in profile['menage']:
                profile['menage']['loyer'] *= 12*7
            if 'cotisation_taxe_habitation' in profile['menage']:
                profile['menage']['cotisation_taxe_habitation'] *= -6
        return profile

    def __compute(self, reference_simulation, reform_simulation, key, month):
        result = []
        for year in self.period_range:
            amount = reference_simulation.calculate(key, '%d%s'%(year,month))[0] - reform_simulation.calculate(key, '%d%s'%(year,month))[0]
            if month == '':
                amount /= 12
            result.append(amount)
        return result

    def __launch_simulation(self, reference_simulation, reform_simulation):
        cotsoc = self.__compute(reference_simulation, reform_simulation, 'cotisations_salariales', '-11')
        csg = self.__compute(reference_simulation, reform_simulation, 'csg', '')
        irpp = self.__compute(reference_simulation, reform_simulation, 'irpp', '')
        ppa = self.__compute(reference_simulation, reform_simulation, 'ppa', '-12')
        aspa = self.__compute(reference_simulation, reform_simulation, 'aspa', '-12')
        apl = self.__compute(reference_simulation, reform_simulation, 'apl', '-12')
        aah = self.__compute(reference_simulation, reform_simulation, 'aah', '-12')
        th = self.__compute(reference_simulation, reform_simulation, 'taxe_habitation', '')
        final = -1*pd.DataFrame([
            np.round(cotsoc),
            np.round(csg),
            np.round(irpp),
            np.round(ppa),
            np.round(aspa),
            np.round(apl),
            np.round(aah),
            np.round(th),
            np.round([ sum(x) for x in zip(*[cotsoc, csg, irpp, ppa, aspa, apl, aah, th]) ]),
        ],index = ["cotsoc","csg","ir","prime_activite","minimum_vieillesse","apl","aah","taxe_habitation","total"],columns = self.period_range)
        return final.to_json()

    def __init_profile(self, scenario, profile):
        scenario.init_single_entity(**profile)
        return scenario
