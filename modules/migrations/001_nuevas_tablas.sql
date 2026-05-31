-- =============================================================
-- Migración 001 – Nuevas tablas y columnas
-- Base de datos: contable_db
-- =============================================================

-- ─────────────────────────────────────────────────────────────
-- 1. Geografía  (copiar datos desde Software_Contable)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `paises` (
  `id_pais`    SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `codigo_iso` VARCHAR(3)        NOT NULL COMMENT 'ISO 3166-1 alpha-3: COL, USA, MEX...',
  `nombre`     VARCHAR(60)       NOT NULL,
  `activo`     TINYINT           NOT NULL DEFAULT 1,
  PRIMARY KEY (`id_pais`),
  UNIQUE KEY `uq_pais_iso` (`codigo_iso`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `departamentos` (
  `id_departamento` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `id_pais`         SMALLINT UNSIGNED NOT NULL,
  `codigo_dane`     INT UNSIGNED      DEFAULT NULL COMMENT 'Codigo DANE para Colombia',
  `nombre`          VARCHAR(60)       NOT NULL,
  PRIMARY KEY (`id_departamento`),
  KEY `fk_depto_pais` (`id_pais`),
  CONSTRAINT `fk_depto_pais`
    FOREIGN KEY (`id_pais`) REFERENCES `paises` (`id_pais`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ciudades` (
  `id_ciudad`       SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `id_departamento` SMALLINT UNSIGNED NOT NULL,
  `codigo_dane`     INT UNSIGNED      DEFAULT NULL,
  `nombre`          VARCHAR(80)       NOT NULL,
  PRIMARY KEY (`id_ciudad`),
  KEY `fk_ciudad_depto` (`id_departamento`),
  CONSTRAINT `fk_ciudad_depto`
    FOREIGN KEY (`id_departamento`) REFERENCES `departamentos` (`id_departamento`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 2. PUC Contenido (descripción + dinámica en HTML unificados)
--    Una sola fila por código; el campo contenido es HTML libre.
--    Formato de ejemplo:
--      <p>Descripción general...</p>
--      <h1>Débitos</h1><p><ul><li>...</li></ul></p>
--      <h1>Créditos</h1><p><ul><li>...</li></ul></p>
--      <h1>Cuentas de detalle</h1><p>110505 - ...<br/>...</p>
--
--    Instrucción para copiar datos desde Software_Contable:
--      Si allá tienes puc_descripciones y puc_dinamicas por separado,
--      puedes unirlas con:
--
--      INSERT INTO contable_db.puc_contenido (codigo, contenido)
--      SELECT d.codigo,
--             CONCAT(d.descripcion, IFNULL(dm.dinamica, ''))
--        FROM Software_Contable.puc_descripciones d
--        LEFT JOIN Software_Contable.puc_dinamicas dm USING (codigo);
--
--    Si ya los tienes en formato unificado (como el ejemplo con
--    <h1>Débitos</h1> etc.), simplemente copia la tabla directamente.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `puc_contenido` (
  `id`        INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `codigo`    VARCHAR(20)  NOT NULL,
  `contenido` LONGTEXT     NOT NULL  COMMENT 'HTML con descripcion, debitos, creditos y cuentas de detalle',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_puc_contenido_codigo` (`codigo`),
  FULLTEXT KEY `ft_puc_contenido` (`contenido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 3. Fuentes Contables
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `fuentes_contables` (
  `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `codigo`      VARCHAR(10)  NOT NULL,
  `descripcion` VARCHAR(200) NOT NULL,
  `tipo_fuente` ENUM(
    'compra','venta','causacion','consignacion',
    'nota debito','nota credito','nota bancaria',
    'prestaciones sociales','nomina','apertura','cierre','ajuste','otro'
  ) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_fuente_codigo` (`codigo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO `fuentes_contables` (`codigo`, `descripcion`, `tipo_fuente`) VALUES
('CO', 'Compras',               'compra'),
('VT', 'Ventas',                'venta'),
('CA', 'Causaciones',           'causacion'),
('CN', 'Consignaciones',        'consignacion'),
('ND', 'Nota Debito',           'nota debito'),
('NC', 'Nota Credito',          'nota credito'),
('NB', 'Nota Bancaria',         'nota bancaria'),
('PS', 'Prestaciones Sociales', 'prestaciones sociales'),
('NO', 'Nomina',                'nomina'),
('AP', 'Apertura',              'apertura'),
('CI', 'Cierre',                'cierre'),
('AJ', 'Ajuste',                'ajuste');

-- ─────────────────────────────────────────────────────────────
-- 4. Nuevas columnas en plan_cuentas
-- ─────────────────────────────────────────────────────────────
ALTER TABLE `plan_cuentas`
  ADD COLUMN IF NOT EXISTS `clase` ENUM(
    'activo','pasivo','patrimonio','ingreso','gasto',
    'costo de venta','costo de produccion',
    'cuentas de orden deudoras','cuentas de orden acreedoras'
  ) NULL AFTER `tipo`,
  ADD COLUMN IF NOT EXISTS `nivel_nombre` ENUM(
    'grupo','cuenta','subcuenta','auxiliar'
  ) NULL AFTER `nivel`,
  ADD COLUMN IF NOT EXISTS `es_retencion` TINYINT(1) NOT NULL DEFAULT 0 AFTER `acepta_mov`,
  ADD COLUMN IF NOT EXISTS `es_impuesto`  TINYINT(1) NOT NULL DEFAULT 0 AFTER `es_retencion`,
  ADD COLUMN IF NOT EXISTS `tarifa_pct`   DECIMAL(8,4)        NULL      AFTER `es_impuesto`,
  ADD COLUMN IF NOT EXISTS `modulo` ENUM(
    'efectivo','cuentas por cobrar','cuentas por pagar',
    'diferida','inventario','nomina','activo fijo','general'
  ) NULL DEFAULT 'general' AFTER `tarifa_pct`;

-- ─────────────────────────────────────────────────────────────
-- 5. fuente_id en asientos
-- ─────────────────────────────────────────────────────────────
ALTER TABLE `asientos`
  ADD COLUMN IF NOT EXISTS `fuente_id` INT UNSIGNED NULL AFTER `periodo_id`;

ALTER TABLE `asientos`
  ADD CONSTRAINT IF NOT EXISTS `fk_asiento_fuente`
    FOREIGN KEY (`fuente_id`) REFERENCES `fuentes_contables` (`id`);

-- ─────────────────────────────────────────────────────────────
-- 6. Geografía en empresas y sedes
-- ─────────────────────────────────────────────────────────────
ALTER TABLE `empresas`
  ADD COLUMN IF NOT EXISTS `id_pais`         SMALLINT UNSIGNED NULL AFTER `ciudad`,
  ADD COLUMN IF NOT EXISTS `id_departamento` SMALLINT UNSIGNED NULL AFTER `id_pais`,
  ADD COLUMN IF NOT EXISTS `id_ciudad`       SMALLINT UNSIGNED NULL AFTER `id_departamento`;

ALTER TABLE `empresas`
  ADD CONSTRAINT IF NOT EXISTS `fk_emp_pais`
    FOREIGN KEY (`id_pais`)         REFERENCES `paises`        (`id_pais`),
  ADD CONSTRAINT IF NOT EXISTS `fk_emp_depto`
    FOREIGN KEY (`id_departamento`) REFERENCES `departamentos` (`id_departamento`),
  ADD CONSTRAINT IF NOT EXISTS `fk_emp_ciudad`
    FOREIGN KEY (`id_ciudad`)       REFERENCES `ciudades`      (`id_ciudad`);

ALTER TABLE `sedes`
  ADD COLUMN IF NOT EXISTS `id_pais`         SMALLINT UNSIGNED NULL AFTER `ciudad`,
  ADD COLUMN IF NOT EXISTS `id_departamento` SMALLINT UNSIGNED NULL AFTER `id_pais`,
  ADD COLUMN IF NOT EXISTS `id_ciudad`       SMALLINT UNSIGNED NULL AFTER `id_departamento`;

ALTER TABLE `sedes`
  ADD CONSTRAINT IF NOT EXISTS `fk_sede_pais`
    FOREIGN KEY (`id_pais`)         REFERENCES `paises`        (`id_pais`),
  ADD CONSTRAINT IF NOT EXISTS `fk_sede_depto`
    FOREIGN KEY (`id_departamento`) REFERENCES `departamentos` (`id_departamento`),
  ADD CONSTRAINT IF NOT EXISTS `fk_sede_ciudad`
    FOREIGN KEY (`id_ciudad`)       REFERENCES `ciudades`      (`id_ciudad`);

-- =============================================================
-- FIN DE MIGRACIÓN
-- =============================================================

-- Migración: columna monto en conceptos_nomina
ALTER TABLE `conceptos_nomina`
  ADD COLUMN IF NOT EXISTS `monto`        DECIMAL(14,2) NULL     COMMENT 'Valor predeterminado para conceptos manuales',
  ADD COLUMN IF NOT EXISTS `es_manual`    TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '1=valor manual, 0=porcentaje';
