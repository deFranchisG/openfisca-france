# -*- coding: utf-8 -*-

from numpy import (
    maximum as max_,
    minimum as min_,
    )


from ...base import *  # noqa analysis:ignore
from ...prestations.prestations_familiales.base_ressource import nb_enf
from .grille import get_indice


class corps(Variable):
    column = StrCol()
    entity_class = Individus
    label = u"Corps (FPE, FPT), cadre d'emploi (FPH)"


class echelon(Variable):
    column = IntCol()
    entity_class = Individus
    label = u"Echelon dans le grade de la fonction publique"


class grade(Variable):
    column = IntCol()
    entity_class = Individus
    label = u"Grade de la fonction publique"


class indemnite_residence(Variable):
    column = FloatCol
    entity_class = Individus
    label = u"Indemnité de résidence des fonctionnaires"

    def function(self, simulation, period):
        period = period.start.period(u'month').offset('first-of')
        traitement_indiciaire_brut = simulation.calculate('traitement_indiciaire_brut', period)
        salaire_de_base = simulation.calculate('salaire_de_base', period)
        categorie_salarie = simulation.calculate('categorie_salarie', period)
        zone_apl_individu = simulation.calculate('zone_apl_individu', period)
        _P = simulation.legislation_at(period.start)

        zone_apl = zone_apl_individu  # TODO: ces zones ne correpondent pas aux zones APL
        P = _P.fonc.indem_resid
        min_zone_1, min_zone_2, min_zone_3 = P.min * P.taux.zone1, P.min * P.taux.zone2, P.min * P.taux.zone3
        taux = P.taux.zone1 * (zone_apl == 1) + P.taux.zone2 * (zone_apl == 2) + P.taux.zone3 * (zone_apl == 3)
        plancher = min_zone_1 * (zone_apl == 1) + min_zone_2 * (zone_apl == 2) + min_zone_3 * (zone_apl == 3)

        return period, max_(
            plancher,
            taux * (traitement_indiciaire_brut + salaire_de_base)
            ) * (categorie_salarie >= 2)


class indice_majore(Variable):
    column = IntCol()
    entity_class = Individus
    label = u"Indice majoré échelon fonctionnaire"

    def function(self, simulation, period):
        period = period.this_month
        categorie_salarie = simulation.calculate('categorie_salarie', period)
        corps = simulation.calculate('corps', period)
        grade = simulation.calculate('grade', period)
        echelon= simulation.calculate('echelon', period)
        return period, get_indice(self, period, categorie_salarie, corps, grade, echelon) 
        

#class indice_majore(Variable):
#    column = FloatCol
#    entity_class = Individus
#    label = u"Indice majoré"
#
#    def function(self, simulation, period):
#        period = period.start.period(u'month').offset('first-of')
#        categorie_salarie = simulation.calculate('categorie_salarie', period)
#        traitement_indiciaire_brut = simulation.calculate('traitement_indiciaire_brut', period)
#        _P = simulation.legislation_at(period.start)
#
#        traitement_annuel_brut = _P.fonc.IM_100
#        return period, (traitement_indiciaire_brut * 100 * 12 / traitement_annuel_brut) * (categorie_salarie >= 2)


class primes_fonction_publique(Variable):
    column = FloatCol
    entity_class = Individus
    label = u"Calcul des primes pour les fonctionnaries"
    url = u"http://vosdroits.service-public.fr/particuliers/F465.xhtml"

    def function(self, simulation, period):
        period = period.start.period(u'month').offset('first-of')
        categorie_salarie = simulation.calculate('categorie_salarie', period)

        traitement_indiciaire_brut = simulation.calculate('traitement_indiciaire_brut', period)
        public = (
            (categorie_salarie == CAT['public_titulaire_etat']) +
            (categorie_salarie == CAT['public_titulaire_territoriale']) +
            (categorie_salarie == CAT['public_titulaire_hospitaliere'])
            )
        return period, TAUX_DE_PRIME * traitement_indiciaire_brut * public


class af_nbenf_fonc(Variable):
    column = IntCol
    entity_class = Familles
    label = u"Nombre d'enfants dans la famille au sens des allocations familiales pour le fonctionnaires"
    # Hack pour éviter une boucle infinie

    def function(self, simulation, period):
        # Note : Cette variable est "instantanée" : quelque soit la période demandée, elle retourne la valeur au premier
        # jour, sans changer la période.
        age_holder = simulation.compute('age', period)
        salaire_de_base = simulation.calculate_add('salaire_de_base', period.start.period('month', 6).offset(-6))
        law = simulation.legislation_at(period.start)
        nbh_travaillees = 169
        smic_mensuel_brut = law.cotsoc.gen.smic_h_b * nbh_travaillees
        autonomie_financiere_holder = (salaire_de_base / 6) >= (law.fam.af.seuil_rev_taux * smic_mensuel_brut)
        age = self.split_by_roles(age_holder, roles = ENFS)
        autonomie_financiere = self.split_by_roles(autonomie_financiere_holder, roles = ENFS)
        af_nbenf = nb_enf(age, autonomie_financiere, law.fam.af.age1, law.fam.af.age2)

        return period, af_nbenf


class supp_familial_traitement(Variable):
    column = FloatCol
    entity_class = Individus
    label = u"Supplément familial de traitement"
    # Attention : par hypothèse ne peut êre attribué qu'à la tête du ménage
    # TODO: gérer le cas encore problématique du conjoint fonctionnaire

    def function(self, simulation, period):
        period = period.start.period(u'month').offset('first-of')
        categorie_salarie = simulation.calculate('categorie_salarie', period)
        traitement_indiciaire_brut = simulation.calculate('traitement_indiciaire_brut', period)
        af_nbenf_fonc_holder = simulation.compute('af_nbenf_fonc', period)
        _P = simulation.legislation_at(period.start)

        fonc_nbenf = self.cast_from_entity_to_role(af_nbenf_fonc_holder, role = CHEF)
        P = _P.fonc.supp_fam
        part_fixe_1 = P.fixe.enf1
        part_fixe_2 = P.fixe.enf2
        part_fixe_supp = P.fixe.enfsupp
        part_fixe = (
            part_fixe_1 * (fonc_nbenf == 1) + part_fixe_2 * (fonc_nbenf == 2) +
            part_fixe_supp * max_(0, fonc_nbenf - 2)
            )
        # pct_variable_1 = 0
        pct_variable_2 = P.prop.enf2
        pct_variable_3 = P.prop.enf3
        pct_variable_supp = P.prop.enfsupp
        pct_variable = (
            pct_variable_2 * (fonc_nbenf == 2) + (pct_variable_3) * (fonc_nbenf == 3) +
            pct_variable_supp * max_(0, fonc_nbenf - 3))

        indice_maj_min = P.IM_min
        indice_maj_max = P.IM_max

        traitement_brut_mensuel_min = _traitement_brut_mensuel(indice_maj_min, _P)
        plancher_mensuel_1 = part_fixe
        plancher_mensuel_2 = part_fixe + traitement_brut_mensuel_min * pct_variable_2
        plancher_mensuel_3 = part_fixe + traitement_brut_mensuel_min * pct_variable_3
        plancher_mensuel_supp = traitement_brut_mensuel_min * pct_variable_supp

        plancher = (plancher_mensuel_1 * (fonc_nbenf == 1) +
                    plancher_mensuel_2 * (fonc_nbenf == 2) +
                    plancher_mensuel_3 * (fonc_nbenf >= 3) +
                    plancher_mensuel_supp * max_(0, fonc_nbenf - 3))

        traitement_brut_mensuel_max = _traitement_brut_mensuel(indice_maj_max, _P)
        plafond_mensuel_1 = part_fixe
        plafond_mensuel_2 = part_fixe + traitement_brut_mensuel_max * pct_variable_2
        plafond_mensuel_3 = part_fixe + traitement_brut_mensuel_max * pct_variable_3
        plafond_mensuel_supp = traitement_brut_mensuel_max * pct_variable_supp

        plafond = (plafond_mensuel_1 * (fonc_nbenf == 1) + plafond_mensuel_2 * (fonc_nbenf == 2) +
                   plafond_mensuel_3 * (fonc_nbenf == 3) +
                   plafond_mensuel_supp * max_(0, fonc_nbenf - 3))

        sft = min_(max_(part_fixe + pct_variable * traitement_indiciaire_brut, plancher), plafond) * (categorie_salarie >= 2)
        # Nota Bene:
        # categorie_salarie is an EnumCol which enum is:
        # CAT = Enum(['prive_non_cadre',
        #             'prive_cadre',
        #             'public_titulaire_etat',
        #             'public_titulaire_militaire',
        #             'public_titulaire_territoriale',
        #             'public_titulaire_hospitaliere',
        #             'public_non_titulaire'])
        return period, sft


class remuneration_principale(Variable):
    column = FloatCol
    entity_class = Individus
    label = u"Rémunération principale des agents titulaires de la fonction publique"

    def function(self, simulation, period):
        traitement_indiciaire_brut = simulation.calculate_add('traitement_indiciaire_brut', period)
        nouvelle_bonification_indiciaire = simulation.calculate('nouvelle_bonification_indiciaire', period)
        categorie_salarie = simulation.calculate('categorie_salarie', period)
        return period, (
            (categorie_salarie >= 2) * (categorie_salarie <= 5) * (
                traitement_indiciaire_brut + nouvelle_bonification_indiciaire
                )
            )


def _traitement_brut_mensuel(indice_maj, law):
    Indice_majore_100_annuel = law.fonc.IM_100
    traitement_brut = Indice_majore_100_annuel * indice_maj / 100 / 12
    return traitement_brut



class traitement_indiciaire_brut(Variable):
    column = FloatCol()
    entity_class = Individus
    label = u"Traitement indiciaire brut (TIB) mensuel"

    def function(self, simulation, period):
        period = period.this_month
        categorie_salarie = simulation.calculate('categorie_salarie', period)
        indice_majore = simulation.calculate('indice_majore', period)
        traitement_indice_majore_100 = simulation.legislation_at(period.start).cotsoc.sal.fonc.commun.pt_ind * 100
        return period, (categorie_salarie >= 2) * (categorie_salarie <= 5) * indice_majore * traitement_indice_majore_100 / 1200
        
        
class IM_an_moyen(Variable):
    column = FloatCol
    entity_class = Individus    
    label = u"Indice majoré annuel moyen"
    
    def function(self, simulation, period):
       # to code
       return period, self

       
class tib_annuel_moyen(Variable):
    column = FloatCol
    entity_class = Individus
    label = u"Traitement indiciaire brut annuel moyen "    
    
    def function(self, simulation, period):     
       #law = simulation.legislation_at(period.start)
       valeur_moyenne_point = 2  # law.fonc.pt_ind_annuel_moyen ## TO ADD valeur moyenne point d'indice (Barèmes IPP MdT)
       indice_majore_moyen = 1000  # simulation.calculate('IM_moyen', period) 
       return period, indice_majore_moyen * valeur_moyenne_point

        
#class gipa(Variable):
#    column = FloatCol
#    entity_class = Individus
#    label = u"Indemnité de garantie individuelle du pouvoir d'achat"
#    
#    def function(self, simulation, period):
#        period = period.start.offset('last-of', 'year').period('month')
#        law = simulation.legislation_at(period.start)
#        inflation = law.fonc.inflation_moyenne_periode_gipa ## TO ADD valeur de l'inflation pour GIPA (Barèmes IPP MdT)
#        traitement_indiciaire_brut_moyen_debut = simulation.calculate(
#            'tib_annuel_moyen', period.offset('first-of', 'year').start.period('year').offset(-3))
#        traitement_indiciaire_brut_moyen_fin = simulation.calculate('tib_annuel_moyen', period)
#        return period, traitement_indiciaire_brut_moyen_debut * (1 + inflation) - traitement_indiciaire_brut_moyen_fin
#