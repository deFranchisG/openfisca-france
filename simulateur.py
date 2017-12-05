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
        self.period = 'year:2017:6'
        self.period_range = range(2018, 2023)

    def run(self, profile):
        profile = self.__format_profile(profile)
        reform_simulation = self.__init_profile(self.reform.new_scenario(), profile).new_simulation()
        reference_simulation = self.__init_profile(self.tax_benefit_system.new_scenario(), profile).new_simulation()
        return self.__launch_simulation(reference_simulation, reform_simulation)

    def __inverse_prive(self, x):
        pss = 3269
        seuil_1 = pss*(1-0.2221)
        seuil_2 = pss*(1-0.2221) + (3*pss-pss)*(1-0.2041)
        seuil_3 = pss*(1-0.2221) + (3*pss-pss)*(1-0.2041) + (4*pss-3*pss)*(1-0.1141)

        if x < seuil_1:
            res = x/(1-0.2221)
        elif (x < seuil_2):
            res = seuil_1/(1-0.2221) + (x-seuil_1)/(1-0.2041)
        elif x < seuil_3:
            res = seuil_1/(1-0.2221) + (seuil_2-seuil_1)/(1-0.2041) + (x-seuil_2)/(1-0.1141)
        else:
            res = seuil_1/(1-0.2221) + (seuil_2-seuil_1)/(1-0.2041) + (seuil_3-seuil_2)/(1-0.1141) + (x-seuil_3)/(1-0.0901)
        return res

    def __inverse_fonctionnaire(self, x):
        if x < 258.072882:
            res = x/(1-0.1056-0.0005-0.9825*0.08-0.01*(1-0.1056))-3.13*(1-0.9825*0.08)
        elif (x < 1166):
            res = x/(1.01*(1-0.9825*0.08)-0.1056-0.0005)
        elif x < 10664.39332:#seuil à 4 pss pour la CSG
            res = x/(1.01*(1-0.9825*0.08)-0.1056-(1-0.1056)*0.01-0.0005)
        elif x < 11498.8564:
            res = 10664.39332/(1.01*(1-0.9825*0.08)-0.1056-(1-0.1056)*0.01-0.0005) + (x-10664.39332)/(1.01*(1-0.9825*0.08)-0.1056-(1-0.1056)*0.01-0.0005)
        else:
            res = 10664.39332/(1.01*(1-0.9825*0.08)-0.1056-(1-0.1056)*0.01-0.0005) + (11498.8564-10664.39332)/(1.01*(1-0.9825*0.08)-0.1056-(1-0.1056)*0.01-0.0005) + (x-11498.8564)/(1.01*(1-0.08)-0.1056-0.0005)
        return res

    def __inverse_salaire(self, x,statut):
        if statut == "public_titulaire_etat":
            res = self.__inverse_fonctionnaire(x)
        elif statut == "prive_non_cadre":
            res = self.__inverse_prive(x)
        return res

    def __inverse_chomage(self, x):
        res = x/(1-0.07)
        return res

    def __inverse_retraite(self, x):
        res = x/(1-0.074)
        return res

    def __format_profile(self, profile):
        profile['period'] = self.period
        profile['enfants'] = [{'age': 9} for _ in range(0, profile['enfants'])]
        for key in ['parent1', 'parent2']:
            if key in profile:
                if 'salaire_de_base' in profile[key]:
                    profile[key]['salaire_de_base'] = self.__inverse_salaire(profile[key]['salaire_de_base'], profile[key]['categorie_salarie'])*12*6
                if 'retraite_brute' in profile[key]:
                    profile[key]['retraite_brute'] = self.__inverse_retraite(profile[key]['retraite_brute'])*12*6
                if 'chomage_brut' in profile[key]:
                    profile[key]['chomage_brut'] = self.__inverse_chomage(profile[key]['chomage_brut'])*12*6
        if 'menage' in profile:
            if 'loyer' in profile['menage']:
                profile['menage']['loyer'] *= 12*6
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
        th = self.__compute(reference_simulation, reform_simulation, 'taxe_habitation', '')
        final = -1*pd.DataFrame([
            np.round(cotsoc),
            np.round(csg),
            np.round(irpp),
            np.round(ppa),
            np.round(aspa),
            np.round([0.,0.,0.,0.,0.]),
            np.round([0.,0.,0.,0.,0.]),
            np.round(th),
            np.round([ sum(x) for x in zip(*[cotsoc, csg, irpp, ppa, aspa, th]) ]),
        ],index = ["cotsoc","csg","ir","prime_activite","minimum_vieillesse","paje","aah","taxe_habitation","total"],columns = self.period_range)
        return final.to_json()

    def __init_profile(self, scenario, profile):
        scenario.init_single_entity(**profile)
        return scenario
