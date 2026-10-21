-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Servidor: 127.0.0.1
-- Tiempo de generación: 16-07-2026 a las 23:53:29
-- Versión del servidor: 10.4.32-MariaDB
-- Versión de PHP: 8.0.30

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de datos: `escuela_db`
--

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `inscripciones`
--

CREATE TABLE `inscripciones` (
  `id` int(11) NOT NULL,
  `nombre` text NOT NULL,
  `apellido` text NOT NULL,
  `ano_cursado` text NOT NULL,
  `cedula` text NOT NULL,
  `repMadre_nombre` text NOT NULL,
  `repMadre_apellido` text NOT NULL,
  `repMadre_cedula` text NOT NULL,
  `repPadre_nombre` text NOT NULL,
  `repPadre_apellido` text NOT NULL,
  `repPadre_cedula` text NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

--
-- Índices para tablas volcadas
--

--
-- Indices de la tabla `inscripciones`
--
ALTER TABLE `inscripciones`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT de las tablas volcadas
--

--
-- AUTO_INCREMENT de la tabla `inscripciones`
--
ALTER TABLE `inscripciones`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- Archivos adjuntos de cada expediente de inscripción
--

CREATE TABLE IF NOT EXISTS `archivos_inscripcion` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `inscripcion_id` int(11) NOT NULL,
  `tipo` varchar(100) NOT NULL,
  `nombre_archivo` varchar(255) NOT NULL,
  `nombre_original` varchar(255) NOT NULL,
  `extension` varchar(10) NOT NULL,
  `creado_en` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_archivos_inscripcion` (`inscripcion_id`),
  CONSTRAINT `fk_archivos_inscripcion`
    FOREIGN KEY (`inscripcion_id`) REFERENCES `inscripciones` (`id`)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `usuarios`
--

CREATE TABLE IF NOT EXISTS `usuarios` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `usuario` varchar(50) NOT NULL UNIQUE,
  `password` varchar(255) NOT NULL,
  `rol` varchar(50) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

UPDATE `usuarios` AS usuario_anterior
LEFT JOIN `usuarios` AS usuario_nuevo
  ON usuario_nuevo.`usuario` = 'administracion'
SET usuario_anterior.`usuario` = 'administracion'
WHERE usuario_anterior.`usuario` = 'administracionGRU'
  AND usuario_nuevo.`id` IS NULL;

UPDATE `usuarios`
SET `rol` = 'administracionGRU'
WHERE `usuario` = 'administracion';

--
-- Volcado de datos para la tabla `usuarios`
--

INSERT INTO `usuarios` (`usuario`, `password`, `rol`) VALUES
('desarrollador', 'scrypt:32768:8:1$JtExvx5ATue7p9Bp$bf3c107f35816660201ae65dc48ea016a32382d80afdf7a5fcc87bcc8daf22a38f96d333827b272b7bb2e082a9ccfa747c80741db9511aab29de182a888b2811', 'desarrollador'),
('directoraGRU', 'scrypt:32768:8:1$cxx2lyTY7xuYdSJH$964be82cbec552137cb849e4a49d71f608ee7f2a5f6677c3bace8a817bf236cca8eba77f654339d5b0d72a6b65577ad4e1919248ca8de8707c5e0a8bb3ff41de', 'directora'),
('administracion', 'scrypt:32768:8:1$A4sBGE7eXiDCzSkd$65787172c83b671b3753a0823a735a9b18d21925eb19729fa3650e5df40250aec31d655d4b3b7d28f05ec1c70b2c2bc890373c8a94282a7857ee3f6d7a6a9f9c', 'administracionGRU')
ON DUPLICATE KEY UPDATE `password` = VALUES(`password`), `rol` = VALUES(`rol`);

COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
