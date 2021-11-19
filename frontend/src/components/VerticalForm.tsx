import React from "react";
import { useForm } from "react-hook-form";

type VerticalFromProps = {
  defaultValues?: Object;
  resolver?: any;
  children?: any;
  onSubmit?: (value: { [key: string]: any }) => void;
  formClass?: string;
};

const VerticalForm = ({
  defaultValues,
  resolver,
  children,
  onSubmit,
  formClass,
}: VerticalFromProps) => {
  /*
   * form methods
   */
  const methods = useForm({ defaultValues, resolver });
  const {
    handleSubmit,
    register,
    control,
    formState: { errors },
  } = methods;

  return (
    <form
      onSubmit={handleSubmit(
        onSubmit
          ? onSubmit
          : () => {
              console.warn("No onSumbit() prop provided for VerticalForm.");
            }
      )}
      className={formClass}
      noValidate
    >
      {Array.isArray(children)
        ? children.map((child) => {
            return child.props && child.props.name
              ? React.createElement(child.type, {
                  ...{
                    ...child.props,
                    register,
                    key: child.props.name,
                    errors,
                    control,
                  },
                })
              : child;
          })
        : children}
    </form>
  );
};

export default VerticalForm;
