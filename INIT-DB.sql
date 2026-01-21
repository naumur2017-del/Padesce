/* 0. Se placer sur master (surtout pas PADESCE) */
USE master;
GO

/* 1. Si la base PADESCE existe, on la force en SINGLE_USER puis on la supprime */
IF DB_ID('PADESCE') IS NOT NULL
BEGIN
    ALTER DATABASE PADESCE SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE PADESCE;
END;
GO

/* 2. Recréation propre de la base */
CREATE DATABASE PADESCE;
GO

/* 3. Se placer sur la base PADESCE */
USE PADESCE;
GO


/* =========================================================
   1. Suppression des tables existantes (enfants -> parents)
      (idempotent : ne plante pas si la table n'existe pas)
   ========================================================= */

IF OBJECT_ID('EnqueteEnvironnement', 'U') IS NOT NULL DROP TABLE EnqueteEnvironnement;
IF OBJECT_ID('EnqueteSatisfactionFormateur', 'U') IS NOT NULL DROP TABLE EnqueteSatisfactionFormateur;
IF OBJECT_ID('EnqueteSatisfactionApprenant', 'U') IS NOT NULL DROP TABLE EnqueteSatisfactionApprenant;
IF OBJECT_ID('EnquetePresence', 'U') IS NOT NULL DROP TABLE EnquetePresence;
IF OBJECT_ID('Apprenant', 'U') IS NOT NULL DROP TABLE Apprenant;
IF OBJECT_ID('Classe', 'U') IS NOT NULL DROP TABLE Classe;
IF OBJECT_ID('Prestation', 'U') IS NOT NULL DROP TABLE Prestation;
IF OBJECT_ID('Formateur', 'U') IS NOT NULL DROP TABLE Formateur;
IF OBJECT_ID('Lieu', 'U') IS NOT NULL DROP TABLE Lieu;
IF OBJECT_ID('Inspecteur', 'U') IS NOT NULL DROP TABLE Inspecteur;
IF OBJECT_ID('Beneficiaire', 'U') IS NOT NULL DROP TABLE Beneficiaire;
IF OBJECT_ID('Formation', 'U') IS NOT NULL DROP TABLE Formation;
IF OBJECT_ID('Prestataire', 'U') IS NOT NULL DROP TABLE Prestataire;
GO

/* =========================================================
   2. Création des tables (parents -> enfants)
   ========================================================= */

/* ---------- Prestataire ---------- */
CREATE TABLE Prestataire (
    id               INT IDENTITY(1,1) PRIMARY KEY,
    code_prestataire NVARCHAR(50) NOT NULL UNIQUE,
    raison_sociale   NVARCHAR(200) NOT NULL,
    type_structure   NVARCHAR(100) NULL,
    telephone        NVARCHAR(50) NULL,
    email            NVARCHAR(150) NULL
);
GO

/* ---------- Formation ---------- */
CREATE TABLE Formation (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    code_formation  NVARCHAR(50) NOT NULL UNIQUE,
    nom_formation   NVARCHAR(200) NOT NULL,
    nom_harmonise   NVARCHAR(200) NULL,
    statut          NVARCHAR(20) NOT NULL,  -- NON_DEMARRE / EN_COURS / TERMINEE
    email           NVARCHAR(150) NULL,
    CONSTRAINT CK_Formation_Statut
        CHECK (statut IN ('NON_DEMARRE','EN_COURS','TERMINEE'))
);
GO

/* ---------- Beneficiaire (structure) ---------- */
CREATE TABLE Beneficiaire (
    id                INT IDENTITY(1,1) PRIMARY KEY,
    nom_structure     NVARCHAR(200) NOT NULL,
    type_structure    NVARCHAR(100) NULL, -- GIC, Association, etc.
    region            NVARCHAR(100) NULL,
    departement       NVARCHAR(100) NULL,
    arrondissement    NVARCHAR(100) NULL,
    ville             NVARCHAR(100) NULL,
    adresse_detaillee NVARCHAR(255) NULL,
    contact           NVARCHAR(100) NULL,
    email             NVARCHAR(150) NULL
);
GO

/* ---------- Inspecteur ---------- */
CREATE TABLE Inspecteur (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    code_inspecteur NVARCHAR(50) NOT NULL UNIQUE,
    nom_complet     NVARCHAR(200) NOT NULL,
    telephone       NVARCHAR(50) NULL,
    email           NVARCHAR(150) NULL
);
GO

/* ---------- Lieu / Site / Salle ---------- */
CREATE TABLE Lieu (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    code_lieu       NVARCHAR(50) NOT NULL UNIQUE,
    nom_lieu        NVARCHAR(200) NOT NULL,
    ville           NVARCHAR(100) NULL,
    arrondissement  NVARCHAR(100) NULL,
    departement     NVARCHAR(100) NULL,
    region          NVARCHAR(100) NULL,
    autre_precision NVARCHAR(255) NULL
);
GO

/* ---------- Formateur ---------- */
CREATE TABLE Formateur (
    id                    INT IDENTITY(1,1) PRIMARY KEY,
    code_formateur        NVARCHAR(50) NOT NULL UNIQUE,
    nom_complet           NVARCHAR(200) NOT NULL,
    specialite            NVARCHAR(200) NULL,
    qualification         NVARCHAR(200) NULL,
    nb_annees_experience  INT NULL,
    fenetre               NVARCHAR(20) NULL,  -- Fenêtre 2/3
    telephone             NVARCHAR(50) NULL,
    ville_residence       NVARCHAR(100) NULL,
    autres_infos_utiles   NVARCHAR(255) NULL
);
GO

/* ---------- Prestation ---------- */
CREATE TABLE Prestation (
    id                                INT IDENTITY(1,1) PRIMARY KEY,
    id_prestataire                    INT NOT NULL,
    id_formation                      INT NOT NULL,
    id_beneficiaire                   INT NULL,  -- si on associe à une structure
    effectif_a_former                 INT NULL,
    nb_femmes                         INT NULL,
    cout_unitaire_PSOAF               DECIMAL(18,2) NULL,
    montant_formation_PSOAF_TTC       DECIMAL(18,2) NULL,
    cout_unitaire_subvention_MCDC_TTC DECIMAL(18,2) NULL,
    montant_total_subvention_MCDC_TTC DECIMAL(18,2) NULL,
    CONSTRAINT FK_Prestation_Prestataire  FOREIGN KEY (id_prestataire)  REFERENCES Prestataire(id),
    CONSTRAINT FK_Prestation_Formation    FOREIGN KEY (id_formation)    REFERENCES Formation(id),
    CONSTRAINT FK_Prestation_Beneficiaire FOREIGN KEY (id_beneficiaire) REFERENCES Beneficiaire(id),
    CONSTRAINT CK_Prestation_Effectifs CHECK (
        (effectif_a_former IS NULL OR effectif_a_former >= 0) AND
        (nb_femmes IS NULL OR nb_femmes >= 0)
    )
);
GO

/* ---------- Classe (session de formation) ---------- */
CREATE TABLE Classe (
    id                  INT IDENTITY(1,1) PRIMARY KEY,
    code_classe         NVARCHAR(50) NOT NULL UNIQUE,
    id_prestation       INT NULL,
    id_lieu             INT NULL,
    id_formation        INT NOT NULL,
    id_formateur        INT NULL,
    intitule_formation  NVARCHAR(200) NULL,
    lieu_texte          NVARCHAR(200) NULL,
    fenetre             NVARCHAR(20) NULL,  -- Fenêtre 2 / 3
    CONSTRAINT FK_Classe_Prestation FOREIGN KEY (id_prestation) REFERENCES Prestation(id),
    CONSTRAINT FK_Classe_Lieu       FOREIGN KEY (id_lieu)       REFERENCES Lieu(id),
    CONSTRAINT FK_Classe_Formation  FOREIGN KEY (id_formation)  REFERENCES Formation(id),
    CONSTRAINT FK_Classe_Formateur  FOREIGN KEY (id_formateur)  REFERENCES Formateur(id)
);
GO

/* ---------- Apprenant ---------- */
CREATE TABLE Apprenant (
    id                   INT IDENTITY(1,1) PRIMARY KEY,
    code_apprenant       NVARCHAR(50) NOT NULL UNIQUE,
    id_classe            INT NULL,  -- lien direct avec Classe
    nom_complet          NVARCHAR(200) NOT NULL,
    genre                NVARCHAR(10) NULL, -- M / F / Autre
    age                  INT NULL,
    fonction             NVARCHAR(200) NULL,
    qualification        NVARCHAR(200) NULL,
    nb_annees_experience INT NULL,
    fenetre              NVARCHAR(20) NULL,
    telephone            NVARCHAR(50) NULL,
    ville_residence      NVARCHAR(100) NULL,
    code                 NVARCHAR(50) NULL, -- code interne éventuel
    CONSTRAINT FK_Apprenant_Classe      FOREIGN KEY (id_classe) REFERENCES Classe(id),
    CONSTRAINT CK_Apprenant_Age         CHECK (age IS NULL OR age >= 0),
    CONSTRAINT CK_Apprenant_Experience  CHECK (nb_annees_experience IS NULL OR nb_annees_experience >= 0)
);
GO

/* ---------- Enquête de présence ---------- */
CREATE TABLE EnquetePresence (
    id                   INT IDENTITY(1,1) PRIMARY KEY,
    id_classe            INT NOT NULL,
    id_apprenant         INT NOT NULL,
    id_inspecteur        INT NULL,
    id_enqueteur         NVARCHAR(100) NULL,  -- nom ou code
    date_enquete         DATE NOT NULL,
    jour                 NVARCHAR(20) NULL,
    heure_debut          TIME(0) NULL,
    heure_fin            TIME(0) NULL,
    presence_code        NVARCHAR(2) NOT NULL,   -- PR / AB
    statut               NVARCHAR(20) NOT NULL,  -- PRESENT / ABSENT
    moyen_enregistrement NVARCHAR(1) NULL,       -- C / P
    CONSTRAINT FK_EnqPresence_Classe     FOREIGN KEY (id_classe)    REFERENCES Classe(id),
    CONSTRAINT FK_EnqPresence_Apprenant  FOREIGN KEY (id_apprenant) REFERENCES Apprenant(id),
    CONSTRAINT FK_EnqPresence_Inspecteur FOREIGN KEY (id_inspecteur) REFERENCES Inspecteur(id),
    CONSTRAINT CK_EnqPresence_PresenceCode CHECK (presence_code IN ('PR','AB')),
    CONSTRAINT CK_EnqPresence_Statut       CHECK (statut IN ('PRESENT','ABSENT')),
    CONSTRAINT CK_EnqPresence_Moyen        CHECK (moyen_enregistrement IS NULL OR moyen_enregistrement IN ('C','P'))
);
GO

/* ---------- Enquête satisfaction apprenant ---------- */
CREATE TABLE EnqueteSatisfactionApprenant (
    id                      INT IDENTITY(1,1) PRIMARY KEY,
    id_classe               INT NOT NULL,
    id_apprenant            INT NOT NULL,
    Q1_ClarteExposes        TINYINT NULL,
    Q2_PertinenceContenus   TINYINT NULL,
    Q3_QualiteSupports      TINYINT NULL,
    Q4_Pratique             TINYINT NULL,
    Q5_PedagogieFormateur   TINYINT NULL,
    Q6_DureeAdaptation      TINYINT NULL,
    Q7_Organisation         TINYINT NULL,
    Q8_UtilitePourActivite  TINYINT NULL,
    Q9_SatisfactionGlobale  TINYINT NULL,
    commentaire_general     NVARCHAR(MAX) NULL,
    recommandations         NVARCHAR(MAX) NULL,
    date_enquete            DATE NOT NULL,
    heure_enquete           TIME(0) NULL,
    id_inspecteur           INT NULL,
    id_enqueteur            NVARCHAR(100) NULL,
    CONSTRAINT FK_EnqSatAp_Classe     FOREIGN KEY (id_classe)    REFERENCES Classe(id),
    CONSTRAINT FK_EnqSatAp_Apprenant  FOREIGN KEY (id_apprenant) REFERENCES Apprenant(id),
    CONSTRAINT FK_EnqSatAp_Inspecteur FOREIGN KEY (id_inspecteur) REFERENCES Inspecteur(id),
    CONSTRAINT CK_EnqSatAp_Notes CHECK (
        (Q1_ClarteExposes       BETWEEN 1 AND 5 OR Q1_ClarteExposes       IS NULL) AND
        (Q2_PertinenceContenus  BETWEEN 1 AND 5 OR Q2_PertinenceContenus  IS NULL) AND
        (Q3_QualiteSupports     BETWEEN 1 AND 5 OR Q3_QualiteSupports     IS NULL) AND
        (Q4_Pratique            BETWEEN 1 AND 5 OR Q4_Pratique            IS NULL) AND
        (Q5_PedagogieFormateur  BETWEEN 1 AND 5 OR Q5_PedagogieFormateur  IS NULL) AND
        (Q6_DureeAdaptation     BETWEEN 1 AND 5 OR Q6_DureeAdaptation     IS NULL) AND
        (Q7_Organisation        BETWEEN 1 AND 5 OR Q7_Organisation        IS NULL) AND
        (Q8_UtilitePourActivite BETWEEN 1 AND 5 OR Q8_UtilitePourActivite IS NULL) AND
        (Q9_SatisfactionGlobale BETWEEN 1 AND 5 OR Q9_SatisfactionGlobale IS NULL)
    )
);
GO

/* ---------- Enquête satisfaction formateur ---------- */
CREATE TABLE EnqueteSatisfactionFormateur (
    id                              INT IDENTITY(1,1) PRIMARY KEY,
    id_classe                       INT NOT NULL,
    id_formateur                    INT NOT NULL,
    Q1_MotivationApprenants         TINYINT NULL,
    Q2_NiveauPrerequis              TINYINT NULL,
    Q3_ImplicationBeneficiaire      TINYINT NULL,
    Q4_OrganisationPrestataire      TINYINT NULL,
    Q5_QualiteInfrastructure        TINYINT NULL,
    Q6_DureeAdaptation              TINYINT NULL,
    Q7_SuiviInspecteur              TINYINT NULL,
    Q8_SoutienMCDC                  TINYINT NULL,
    Q9_SatisfactionGlobalePrestataire TINYINT NULL,
    commentaires                    NVARCHAR(MAX) NULL,
    recommandations                 NVARCHAR(MAX) NULL,
    date_enquete                    DATE NOT NULL,
    heure_enquete                   TIME(0) NULL,
    id_inspecteur                   INT NULL,
    id_enqueteur                    NVARCHAR(100) NULL,
    CONSTRAINT FK_EnqSatForm_Classe     FOREIGN KEY (id_classe)    REFERENCES Classe(id),
    CONSTRAINT FK_EnqSatForm_Formateur  FOREIGN KEY (id_formateur) REFERENCES Formateur(id),
    CONSTRAINT FK_EnqSatForm_Inspecteur FOREIGN KEY (id_inspecteur) REFERENCES Inspecteur(id),
    CONSTRAINT CK_EnqSatForm_Notes CHECK (
        (Q1_MotivationApprenants          BETWEEN 1 AND 5 OR Q1_MotivationApprenants          IS NULL) AND
        (Q2_NiveauPrerequis               BETWEEN 1 AND 5 OR Q2_NiveauPrerequis               IS NULL) AND
        (Q3_ImplicationBeneficiaire       BETWEEN 1 AND 5 OR Q3_ImplicationBeneficiaire       IS NULL) AND
        (Q4_OrganisationPrestataire       BETWEEN 1 AND 5 OR Q4_OrganisationPrestataire       IS NULL) AND
        (Q5_QualiteInfrastructure         BETWEEN 1 AND 5 OR Q5_QualiteInfrastructure         IS NULL) AND
        (Q6_DureeAdaptation               BETWEEN 1 AND 5 OR Q6_DureeAdaptation               IS NULL) AND
        (Q7_SuiviInspecteur               BETWEEN 1 AND 5 OR Q7_SuiviInspecteur               IS NULL) AND
        (Q8_SoutienMCDC                   BETWEEN 1 AND 5 OR Q8_SoutienMCDC                   IS NULL) AND
        (Q9_SatisfactionGlobalePrestataire BETWEEN 1 AND 5 OR Q9_SatisfactionGlobalePrestataire IS NULL)
    )
);
GO

/* ---------- Enquête environnement ---------- */
CREATE TABLE EnqueteEnvironnement (
    id                   INT IDENTITY(1,1) PRIMARY KEY,
    id_lieu              INT NOT NULL,
    id_classe            INT NULL,
    id_inspecteur        INT NULL,
    date_enquete         DATE NOT NULL,
    heure_enregistrement TIME(0) NULL,

    tables_disponibles   BIT NULL,
    chaises_disponibles  BIT NULL,
    ecran                BIT NULL,
    videoprojecteur      BIT NULL,
    ventilation          BIT NULL,
    eclairage            BIT NULL,
    aeration             BIT NULL,
    prises_electriques   BIT NULL,
    salle_propre         BIT NULL,
    salle_accessible     BIT NULL,
    salle_securisee      BIT NULL,
    signaletique         BIT NULL,
    commodite            BIT NULL,
    accessibilite        BIT NULL,
    securite             BIT NULL,
    acces_eau            BIT NULL,

    commentaires_salle   NVARCHAR(MAX) NULL,
    commentaire_global   NVARCHAR(MAX) NULL,
    id_enqueteur         NVARCHAR(100) NULL,

    CONSTRAINT FK_EnqEnv_Lieu       FOREIGN KEY (id_lieu)      REFERENCES Lieu(id),
    CONSTRAINT FK_EnqEnv_Classe     FOREIGN KEY (id_classe)    REFERENCES Classe(id),
    CONSTRAINT FK_EnqEnv_Inspecteur FOREIGN KEY (id_inspecteur) REFERENCES Inspecteur(id)
);
GO
