# -*- coding: utf-8 -*-

from __future__ import division

from numpy import floor

from openfisca_france.model.base import *  # noqa analysis:ignore


class uc(Variable):
    value_type = float
    entity = Menage
    label = u"Unités de consommation"
    definition_period = YEAR

    def formula(self, simulation, period):
        '''
        Calcule le nombre d'unités de consommation du ménage avec l'échelle de l'INSEE
        '''
        age_en_mois_holder = simulation.compute('age_en_mois', period)

        age_en_mois = self.split_by_roles(age_en_mois_holder)

        uc_adt = 0.5
        uc_enf = 0.3
        uc = 0.5
        for agm in age_en_mois.itervalues():
            age = floor(agm / 12)
            adt = (15 <= age) & (age <= 150)
            enf = (0 <= age) & (age <= 14)
            uc += adt * uc_adt + enf * uc_enf
        return uc


class type_menage(Variable):
    value_type = int
    is_period_size_independent = True
    entity = Menage
    label = u"Type de ménage"
    definition_period = YEAR

    def formula(menage, period):
        '''
        Type de menage
        TODO: prendre les enfants du ménage et non ceux de la famille
        '''
        af_nbenf = menage.personne_de_reference.famille('af_nbenf', period.first_month)
        isole = not_(menage.personne_de_reference.famille('en_couple', period.first_month))

        return (
            0 * (isole * (af_nbenf == 0)) +  # Célibataire
            1 * (not_(isole) * (af_nbenf == 0)) +  # Couple sans enfants
            2 * (not_(isole) * (af_nbenf == 1)) +  # Couple un enfant
            3 * (not_(isole) * (af_nbenf == 2)) +  # Couple deux enfants
            4 * (not_(isole) * (af_nbenf == 3)) +  # Couple trois enfants et plus
            5 * (isole * (af_nbenf == 1)) +  # Famille monoparentale un enfant
            6 * (isole * (af_nbenf == 2)) +  # Famille monoparentale deux enfants
            7 * (isole * (af_nbenf == 3))
            )  # Famille monoparentale trois enfants et plus


class revenu_disponible(Variable):
    value_type = float
    entity = Menage
    label = u"Revenu disponible du ménage"
    reference = "http://fr.wikipedia.org/wiki/Revenu_disponible"
    definition_period = YEAR

    def formula(self, simulation, period):
        revenus_du_travail_holder = simulation.compute('revenus_du_travail', period)
        pen_holder = simulation.compute('pensions', period)
        rev_cap_holder = simulation.compute('revenus_du_capital', period)
        prestations_sociales_holder = simulation.compute('prestations_sociales', period)
        ppe_holder = simulation.compute('ppe', period)
        impots_directs = simulation.calculate('impots_directs', period)

        pen = self.sum_by_entity(pen_holder)
        ppe = self.cast_from_entity_to_role(ppe_holder, role = VOUS)
        ppe = self.sum_by_entity(ppe)
        prestations_sociales = self.cast_from_entity_to_role(prestations_sociales_holder, role = CHEF)
        prestations_sociales = self.sum_by_entity(prestations_sociales)
        rev_cap = self.sum_by_entity(rev_cap_holder)
        revenus_du_travail = self.sum_by_entity(revenus_du_travail_holder)

        return revenus_du_travail + pen + rev_cap + prestations_sociales + ppe + impots_directs


class niveau_de_vie(Variable):
    value_type = float
    entity = Menage
    label = u"Niveau de vie du ménage"
    definition_period = YEAR

    def formula(menage, period):
        revenu_disponible = menage('revenu_disponible', period)
        uc = menage('uc', period)
        return revenu_disponible / uc


class revenu_net_individu(Variable):
    value_type = float
    entity = Individu
    label = u"Revenu net de l'individu"
    definition_period = YEAR

    def formula(individu, period):
        pensions = individu('pensions', period)
        revenus_du_capital = individu('revenus_du_capital', period)
        revenus_du_travail = individu('revenus_du_travail', period)

        return pensions + revenus_du_capital + revenus_du_travail


class revenu_net(Variable):
    entity = Menage
    label = u"Revenu net du ménage"
    value_type = float
    reference = u"http://impotsurlerevenu.org/definitions/115-revenu-net-imposable.php",
    definition_period = YEAR

    def formula(menage, period):
        revenu_net_individus = menage.members('revenu_net_individu', period)
        return menage.sum(revenu_net_individus)


class niveau_de_vie_net(Variable):
    value_type = float
    entity = Menage
    label = u"Niveau de vie net du ménage"
    definition_period = YEAR

    def formula(menage, period):
        revenu_net = menage('revenu_net', period)
        uc = menage('uc', period)

        return revenu_net / uc


class revenu_initial_individu(Variable):
    value_type = float
    entity = Individu
    label = u"Revenu initial de l'individu"
    definition_period = YEAR

    def formula(individu, period):
        cotisations_employeur_contributives = individu('cotisations_employeur_contributives', period)
        cotisations_salariales_contributives = individu('cotisations_salariales_contributives', period)
        pensions = individu('pensions', period)
        revenus_du_capital = individu('revenus_du_capital', period)
        revenus_du_travail = individu('revenus_du_travail', period)

        return (revenus_du_travail + pensions + revenus_du_capital - cotisations_employeur_contributives -
            cotisations_salariales_contributives)


class revenu_initial(Variable):
    entity = Menage
    label = u"Revenu initial du ménage"
    value_type = float
    definition_period = YEAR

    def formula(menage, period):
        revenu_initial_individus = menage.members('revenu_initial_individu', period)
        return menage.sum(revenu_initial_individus)


class niveau_de_vie_initial(Variable):
    value_type = float
    entity = Menage
    label = u"Niveau de vie initial du ménage"
    definition_period = YEAR

    def formula(menage, period):
        revenu_initial = menage('revenu_initial', period)
        uc = menage('uc', period)

        return revenu_initial / uc


def _revprim(revenus_du_travail, chomage_imposable, rev_cap, cotisations_employeur, cotisations_salariales):
    '''
    Revenu primaire du ménage
    Ensemble des revenus d'activités superbruts avant tout prélèvement
    Il est égale à la valeur ajoutée produite par les résidents
    'men'
    '''
    return revenus_du_travail + rev_cap - cotisations_employeur - cotisations_salariales - chomage_imposable


class revenus_du_travail(Variable):
    value_type = float
    entity = Individu
    label = u"Revenus du travail (salariés et non salariés)"
    reference = "http://fr.wikipedia.org/wiki/Revenu_du_travail"
    definition_period = YEAR

    def formula(individu, period):
        revenu_assimile_salaire = individu('revenu_assimile_salaire', period)
        rag = individu('rag', period)
        ric = individu('ric', period)
        rnc = individu('rnc', period)

        return revenu_assimile_salaire + rag + ric + rnc


class pensions(Variable):
    value_type = float
    entity = Individu
    label = u"Pensions et revenus de remplacement"
    reference = "http://fr.wikipedia.org/wiki/Rente"
    definition_period = YEAR

    def formula(individu, period):
        chomage_net = individu('chomage_net', period, options = [ADD])
        retraite_nette = individu('retraite_nette', period, options = [ADD])
        pensions_alimentaires_percues = individu('pensions_alimentaires_percues', period, options = [ADD])
        pensions_invalidite = individu('pensions_invalidite', period, options = [ADD])

        # Revenus du foyer fiscal, que l'on projette uniquement sur le 1er déclarant
        foyer_fiscal = individu.foyer_fiscal
        pensions_alimentaires_versees = foyer_fiscal('pensions_alimentaires_versees', period)
        retraite_titre_onereux = foyer_fiscal('retraite_titre_onereux', period, options = [ADD])
        pen_foyer_fiscal = pensions_alimentaires_versees + retraite_titre_onereux
        pen_foyer_fiscal_projetees = pen_foyer_fiscal * (individu.has_role(foyer_fiscal.DECLARANT_PRINCIPAL))

        return (chomage_net + retraite_nette + pensions_alimentaires_percues + pensions_invalidite + pen_foyer_fiscal_projetees)


class cotsoc_bar(Variable):
    value_type = float
    entity = FoyerFiscal
    label = u"Cotisations sociales sur les revenus du capital imposés au barème"
    definition_period = YEAR

    def formula(foyer_fiscal, period):
        csg_cap_bar = foyer_fiscal('csg_cap_bar', period)
        prelsoc_cap_bar = foyer_fiscal('prelsoc_cap_bar', period)
        crds_cap_bar = foyer_fiscal('crds_cap_bar', period)

        return csg_cap_bar + prelsoc_cap_bar + crds_cap_bar


class cotsoc_lib(Variable):
    value_type = float
    entity = FoyerFiscal
    label = u"Cotisations sociales sur les revenus du capital soumis au prélèvement libératoire"
    definition_period = YEAR

    def formula(foyer_fiscal, period):
        csg_cap_lib = foyer_fiscal('csg_cap_lib', period)
        prelsoc_cap_lib = foyer_fiscal('prelsoc_cap_lib', period)
        crds_cap_lib = foyer_fiscal('crds_cap_lib', period)

        return csg_cap_lib + prelsoc_cap_lib + crds_cap_lib


class revenus_du_capital(Variable):
    value_type = float
    entity = Individu
    label = u"Revenus du patrimoine"
    reference = "http://fr.wikipedia.org/wiki/Revenu#Revenu_du_Capital"
    definition_period = YEAR

    def formula(individu, period):

        # Revenus du foyer fiscal, que l'on projette uniquement sur le 1er déclarant
        foyer_fiscal = individu.foyer_fiscal
        fon = foyer_fiscal('fon', period)
        rev_cap_bar = foyer_fiscal('rev_cap_bar', period, options = [ADD])
        cotsoc_lib = foyer_fiscal('cotsoc_lib', period)
        rev_cap_lib = foyer_fiscal('rev_cap_lib', period, options = [ADD])
        imp_lib = foyer_fiscal('imp_lib', period)
        cotsoc_bar = foyer_fiscal('cotsoc_bar', period)

        revenus_foyer_fiscal = fon + rev_cap_bar + cotsoc_lib + rev_cap_lib + imp_lib + cotsoc_bar
        revenus_foyer_fiscal_projetes = revenus_foyer_fiscal * individu.has_role(foyer_fiscal.DECLARANT_PRINCIPAL)

        rac = individu('rac', period)

        return revenus_foyer_fiscal_projetes + rac


class prestations_sociales(Variable):
    value_type = float
    entity = Famille
    label = u"Prestations sociales"
    reference = "http://fr.wikipedia.org/wiki/Prestation_sociale"
    definition_period = YEAR

    def formula(famille, period):
        '''
        Prestations sociales
        '''
        prestations_familiales = famille('prestations_familiales', period)
        minima_sociaux = famille('minima_sociaux', period)
        aides_logement = famille('aides_logement', period)

        return prestations_familiales + minima_sociaux + aides_logement


class prestations_familiales(Variable):
    value_type = float
    entity = Famille
    label = u"Prestations familiales"
    reference = "http://www.social-sante.gouv.fr/informations-pratiques,89/fiches-pratiques,91/prestations-familiales,1885/les-prestations-familiales,12626.html"
    definition_period = YEAR

    def formula(famille, period):
        af = famille('af', period, options = [ADD])
        cf = famille('cf', period, options = [ADD])
        ars = famille('ars', period)
        aeeh = famille('aeeh', period, options = [ADD])
        paje = famille('paje', period, options = [ADD])
        asf = famille('asf', period, options = [ADD])
        crds_pfam = famille('crds_pfam', period)

        return af + cf + ars + aeeh + paje + asf + crds_pfam


class minimum_vieillesse(Variable):
    calculate_output = calculate_output_add
    value_type = float
    entity = Famille
    label = u"Minimum vieillesse (ASI + ASPA)"
    definition_period = YEAR

    def formula(famille, period):
        return famille('asi', period, options = [ADD]) + famille('aspa', period, options = [ADD])


class minima_sociaux(Variable):
    value_type = float
    entity = Famille
    label = u"Minima sociaux"
    reference = "http://fr.wikipedia.org/wiki/Minima_sociaux"
    definition_period = YEAR

    def formula(self, simulation, period):
        aah_holder = simulation.compute_add('aah', period)
        caah_holder = simulation.compute_add('caah', period)
        aefa = simulation.calculate('aefa', period)
        api = simulation.calculate_add('api', period)
        ass = simulation.calculate_add('ass', period)
        minimum_vieillesse = simulation.calculate_add('minimum_vieillesse', period)
        ppa = simulation.calculate_add('ppa', period)
        psa = simulation.calculate_add('psa', period)
        rsa = simulation.calculate_add('rsa', period)

        aah = self.sum_by_entity(aah_holder)
        caah = self.sum_by_entity(caah_holder)

        return aah + caah + minimum_vieillesse + rsa + aefa + api + ass + psa + ppa


class aides_logement(Variable):
    value_type = float
    entity = Famille
    label = u"Allocations logements"
    reference = "http://vosdroits.service-public.fr/particuliers/N20360.xhtml"
    definition_period = YEAR

    def formula(famille, period):
        '''
        Prestations logement
        '''
        apl = famille('apl', period, options = [ADD])
        als = famille('als', period, options = [ADD])
        alf = famille('alf', period, options = [ADD])
        crds_logement = famille('crds_logement', period, options = [ADD])

        return apl + als + alf + crds_logement


class impots_directs(Variable):
    value_type = float
    entity = Menage
    label = u"Impôts directs"
    reference = "http://fr.wikipedia.org/wiki/Imp%C3%B4t_direct"
    definition_period = YEAR

    def formula(self, simulation, period):
        irpp_holder = simulation.compute('irpp', period)
        taxe_habitation = simulation.calculate('taxe_habitation', period)

        irpp = self.cast_from_entity_to_role(irpp_holder, role = VOUS)
        irpp = self.sum_by_entity(irpp)

        return irpp + taxe_habitation


class crds(Variable):
    value_type = float
    entity = Individu
    label = u"Contributions au remboursement de la dette sociale"
    definition_period = YEAR

    def formula(individu, period):
        # CRDS sur revenus individuels
        crds_salaire = individu('crds_salaire', period, options = [ADD])
        crds_retraite = individu('crds_retraite', period, options = [ADD])
        crds_chomage = individu('crds_chomage', period, options = [ADD])
        crds_individu = crds_salaire + crds_retraite + crds_chomage
        # CRDS sur revenus de la famille, projetés seulement sur la première personne
        crds_pfam = individu.famille('crds_pfam', period)
        crds_logement = individu.famille('crds_logement', period, options = [ADD])
        crds_mini = individu.famille('crds_mini', period, options = [ADD])
        crds_famille = crds_pfam + crds_logement + crds_mini
        crds_famille_projetes = crds_famille * individu.has_role(Famille.DEMANDEUR)
        # CRDS sur revenus du foyer fiscal, projetés seulement sur la première personne
        crds_fon = individu.foyer_fiscal('crds_fon', period)
        crds_pv_mo = individu.foyer_fiscal('crds_pv_mo', period)
        crds_pv_immo = individu.foyer_fiscal('crds_pv_immo', period)
        crds_cap_bar = individu.foyer_fiscal('crds_cap_bar', period)
        crds_cap_lib = individu.foyer_fiscal('crds_cap_lib', period)
        crds_foyer_fiscal = crds_fon + crds_pv_mo + crds_pv_immo + crds_cap_bar + crds_cap_lib
        crds_foyer_fiscal_projetee = crds_foyer_fiscal * individu.has_role(FoyerFiscal.DECLARANT_PRINCIPAL)
        return crds_individu + crds_famille_projetes + crds_foyer_fiscal_projetee


class csg(Variable):
    value_type = float
    entity = Individu
    label = u"Contribution sociale généralisée"
    definition_period = YEAR

    def formula(individu, period):
        csg_imposable_salaire = individu('csg_imposable_salaire', period, options = [ADD])
        csg_deductible_salaire = individu('csg_deductible_salaire', period, options = [ADD])
        csg_imposable_chomage = individu('csg_imposable_chomage', period, options = [ADD])
        csg_deductible_chomage = individu('csg_deductible_chomage', period, options = [ADD])
        csg_imposable_retraite = individu('csg_imposable_retraite', period, options = [ADD])
        csg_deductible_retraite = individu('csg_deductible_retraite', period, options = [ADD])
        # CSG prélevée sur les revenus du foyer fiscal, projetés seulement sur la première personne
        csg_fon = individu.foyer_fiscal('csg_fon', period)
        csg_cap_lib = individu.foyer_fiscal('csg_cap_lib', period)
        csg_cap_bar = individu.foyer_fiscal('csg_cap_bar', period)
        csg_pv_mo = individu.foyer_fiscal('csg_pv_mo', period)
        csg_pv_immo = individu.foyer_fiscal('csg_pv_immo', period)
        csg_foyer_fiscal = csg_fon + csg_cap_lib + csg_cap_bar + csg_pv_mo + csg_pv_immo
        csg_foyer_fiscal_projetee = csg_foyer_fiscal * individu.has_role(FoyerFiscal.DECLARANT_PRINCIPAL)

        return (csg_imposable_salaire + csg_deductible_salaire + csg_imposable_chomage +
                csg_deductible_chomage + csg_imposable_retraite + csg_deductible_retraite + csg_foyer_fiscal_projetee)


class cotisations_non_contributives(Variable):
    value_type = float
    entity = Individu
    label = u"Cotisations sociales non contributives"
    definition_period = YEAR

    def formula(individu, period):
        cotisations_employeur_non_contributives = individu('cotisations_employeur_non_contributives',
            period)
        cotisations_salariales_non_contributives = individu('cotisations_salariales_non_contributives',
            period)

        return cotisations_employeur_non_contributives + cotisations_salariales_non_contributives


class prelsoc_cap(Variable):
    value_type = float
    entity = Individu
    label = u"Prélèvements sociaux sur les revenus du capital"
    reference = "http://www.impots.gouv.fr/portal/dgi/public/particuliers.impot?pageId=part_ctrb_soc&paf_dm=popup&paf_gm=content&typePage=cpr02&sfid=501&espId=1&impot=CS"
    definition_period = YEAR

    def formula(individu, period):
        # Prélevements effectués sur les revenus du foyer fiscal
        prelsoc_fon = individu.foyer_fiscal('prelsoc_fon', period)
        prelsoc_cap_lib = individu.foyer_fiscal('prelsoc_cap_lib', period)
        prelsoc_cap_bar = individu.foyer_fiscal('prelsoc_cap_bar', period)
        prelsoc_pv_mo = individu.foyer_fiscal('prelsoc_pv_mo', period)
        prelsoc_pv_immo = individu.foyer_fiscal('prelsoc_pv_immo', period)
        prel_foyer_fiscal = prelsoc_fon + prelsoc_cap_lib + prelsoc_cap_bar + prelsoc_pv_mo + prelsoc_pv_immo

        return prel_foyer_fiscal * individu.has_role(FoyerFiscal.DECLARANT_PRINCIPAL)


class check_csk(Variable):
    value_type = float
    entity = Menage
    label = u"check_csk"
    definition_period = YEAR

    def formula(menage, period):
        foyer_fiscal = menage.personne_de_reference.foyer_fiscal

        # Prélevements effectués sur les revenus du foyer fiscal
        prelsoc_cap_bar = foyer_fiscal('prelsoc_cap_bar', period)
        prelsoc_pv_mo = foyer_fiscal('prelsoc_pv_mo', period)
        prelsoc_fon = foyer_fiscal('prelsoc_fon', period)

        return prelsoc_cap_bar + prelsoc_pv_mo + prelsoc_fon


class check_csg(Variable):
    value_type = float
    entity = Menage
    label = u"check_csg"
    definition_period = YEAR

    def formula(menage, period):
        foyer_fiscal = menage.personne_de_reference.foyer_fiscal
        # CSG prélevée sur les revenus du foyer fiscal
        csg_cap_bar = foyer_fiscal('csg_cap_bar', periop)
        csg_pv_mo = foyer_fiscal('csg_pv_mo', periop)
        csg_fon = foyer_fiscal('csg_fon', periop)

        return csg_cap_bar + csg_pv_mo + csg_fon


class check_crds(Variable):
    value_type = float
    entity = Menage
    label = u"check_crds"
    definition_period = YEAR

    def formula(menage, period):
        foyer_fiscal = menage.personne_de_reference.foyer_fiscal
        # CRDS prélevée sur les revenus du foyer fiscal
        crds_pv_mo = foyer_fiscal('crds_pv_mo', period)
        crds_fon = foyer_fiscal('crds_fon', period)
        crds_cap_bar = foyer_fiscal('crds_cap_bar', period)

        return crds_pv_mo + crds_fon + crds_cap_bar
