-- schema.sql

CREATE TABLE teachers (
    teacher_id  SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL
);

CREATE TABLE students (
    student_id  SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL
);

CREATE TABLE courses (
    course_id   SERIAL PRIMARY KEY,
    title       VARCHAR(150) NOT NULL,
    teacher_id  INT NOT NULL REFERENCES teachers(teacher_id)
);

CREATE TABLE enrollments (
    student_id  INT NOT NULL REFERENCES students(student_id),
    course_id   INT NOT NULL REFERENCES courses(course_id),
    PRIMARY KEY (student_id, course_id)
);
