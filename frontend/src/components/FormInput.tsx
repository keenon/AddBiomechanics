import React, { useState } from "react";
import { Form, InputGroup } from "react-bootstrap";
import classNames from "classnames";

type PasswordInputProps = {
  name?: string;
  placeholder?: string;
  refCallback?: any;
  errors?: { [key: string]: any };
  register?: any;
  className?: string;
};

/* Password Input */
const PasswordInput = ({
  name,
  placeholder,
  refCallback,
  errors,
  register,
  className,
}: PasswordInputProps) => {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <>
      <InputGroup className="mb-0">
        <Form.Control
          type={showPassword ? "text" : "password"}
          placeholder={placeholder}
          name={name}
          id={name}
          as="input"
          ref={(r: HTMLInputElement) => {
            if (refCallback) refCallback(r);
          }}
          className={className}
          isInvalid={errors && name && errors[name] ? true : false}
          {...(register ? register(name) : {})}
          autoComplete={name}
        />
        <div
          className={classNames("input-group-text", "input-group-password", {
            "show-password": showPassword,
          })}
          data-password={showPassword ? "true" : "false"}
        >
          <span
            className="password-eye"
            onClick={() => {
              setShowPassword(!showPassword);
            }}
          ></span>
        </div>
      </InputGroup>
    </>
  );
};

type FormInputProps = {
  label?: string;
  type?: string;
  name?: string;
  placeholder?: string;
  register?: any;
  errors?: { [key: string]: any };
  className?: string;
  labelClassName?: string;
  containerClass?: string;
  refCallback?: any;
  children?: any;
};

const FormInput = ({
  label,
  type,
  name,
  placeholder,
  register,
  errors,
  className,
  labelClassName,
  containerClass,
  refCallback,
  children,
  ...otherProps
}: FormInputProps) => {
  // handle input type
  const comp =
    type === "textarea" ? "textarea" : type === "select" ? "select" : "input";

  return (
    <>
      {type === "hidden" ? (
        <input
          type={type}
          name={name}
          {...(register ? register(name) : {})}
          {...otherProps}
        />
      ) : (
        <>
          {type === "password" ? (
            <>
              <Form.Group className={containerClass}>
                {label ? (
                  <>
                    {" "}
                    <Form.Label className={labelClassName}>
                      {label}
                    </Form.Label>{" "}
                    {children}{" "}
                  </>
                ) : null}
                <PasswordInput
                  name={name}
                  placeholder={placeholder}
                  refCallback={refCallback}
                  errors={errors}
                  register={register}
                  className={className}
                />

                {errors && name && errors[name] ? (
                  <Form.Control.Feedback type="invalid" className="d-block">
                    {errors[name]["message"]}
                  </Form.Control.Feedback>
                ) : null}
              </Form.Group>
            </>
          ) : (
            <>
              {type === "checkbox" || type === "radio" ? (
                <>
                  <Form.Group className={containerClass}>
                    <Form.Check
                      type={type}
                      label={label}
                      name={name}
                      id={name}
                      ref={(r: HTMLInputElement) => {
                        if (refCallback) refCallback(r);
                      }}
                      className={className}
                      isInvalid={errors && name && errors[name] ? true : false}
                      {...(register ? register(name) : {})}
                      {...otherProps}
                    />

                    {errors && name && errors[name] ? (
                      <Form.Control.Feedback type="invalid">
                        {errors[name]["message"]}
                      </Form.Control.Feedback>
                    ) : null}
                  </Form.Group>
                </>
              ) : (
                <Form.Group className={containerClass}>
                  {label ? (
                    <Form.Label className={labelClassName}>{label}</Form.Label>
                  ) : null}

                  <Form.Control
                    type={type}
                    placeholder={placeholder}
                    name={name}
                    id={name}
                    as={comp}
                    ref={(r: HTMLInputElement) => {
                      if (refCallback) refCallback(r);
                    }}
                    className={className}
                    isInvalid={errors && name && errors[name] ? true : false}
                    {...(register ? register(name) : {})}
                    {...otherProps}
                    autoComplete={name}
                  >
                    {children ? children : null}
                  </Form.Control>

                  {errors && name && errors[name] ? (
                    <Form.Control.Feedback type="invalid">
                      {errors[name]["message"]}
                    </Form.Control.Feedback>
                  ) : null}
                </Form.Group>
              )}
            </>
          )}
        </>
      )}
    </>
  );
};

export default FormInput;
