import { mount } from 'enzyme';

import { checkAccessibility } from '../../../test-util/accessibility';
import mockImportedComponents from '../../../test-util/mock-imported-components';
import { waitFor, waitForElement } from '../../../test-util/wait';
import { GradingService, withServices } from '../../services';
import SubmitGradeForm, { $imports } from '../SubmitGradeForm';

describe('SubmitGradeForm', () => {
  const fakeStudent = {
    userid: 'student1',
    displayName: 'Student 1',
    LISResultSourcedId: 1,
    LISOutcomeServiceUrl: '',
  };

  const fakeStudentAlt = {
    userid: 'student2',
    displayName: 'Student 2',
    LISResultSourcedId: 2,
    LISOutcomeServiceUrl: '',
  };

  const fakeGradingService = {
    submitGrade: sinon.stub().resolves({}),
    fetchGrade: sinon.stub().resolves({ currentScore: 1 }),
  };

  const SubmitGradeFormWrapper = withServices(SubmitGradeForm, () => [
    [GradingService, fakeGradingService],
  ]);

  let container;
  const renderForm = (props = {}) => {
    return mount(<SubmitGradeFormWrapper student={fakeStudent} {...props} />, {
      attachTo: container,
    });
  };

  const fakeValidateGrade = sinon.stub();
  const fakeFormatToNumber = sinon.stub();
  const inputSelector = '[data-testid="grade-input"]';

  async function waitForGradeFetch(wrapper) {
    await waitFor(() => {
      wrapper.update();
      return !wrapper.find('Spinner').exists();
    });
    wrapper.update();
  }

  beforeEach(() => {
    // This extra element is necessary to test automatic `focus`-ing
    // of the component's `input` element
    container = document.createElement('div');
    document.body.appendChild(container);

    // Reset the api grade stubs for each test because
    // some tests below will change these for specific cases.
    fakeGradingService.submitGrade.resolves({});
    fakeGradingService.fetchGrade.resolves({ currentScore: 1 });

    $imports.$mock(mockImportedComponents());
    $imports.$mock({
      '../utils/validation': {
        formatToNumber: fakeFormatToNumber,
        validateGrade: fakeValidateGrade,
      },
    });
  });

  afterEach(() => {
    $imports.$restore();
  });

  it('does not disable the input field when the disable prop is missing', () => {
    const wrapper = renderForm();
    assert.isFalse(wrapper.find(inputSelector).prop('disabled'));
  });

  it('disables the submit button when the `student` prop is `null`', () => {
    const wrapper = renderForm({ student: null });
    assert.isTrue(wrapper.find('button[type="submit"]').prop('disabled'));
  });

  it("sets the input key to the student's LISResultSourcedId", () => {
    const wrapper = renderForm();
    assert.equal(
      wrapper.find(inputSelector).key(),
      fakeStudent.LISResultSourcedId
    );
  });

  it('clears out the previous grade when changing students', async () => {
    const wrapper = renderForm();
    await waitForGradeFetch(wrapper);

    assert.strictEqual(wrapper.find(inputSelector).prop('defaultValue'), '10');
    wrapper.setProps({ student: fakeStudentAlt });
    assert.strictEqual(wrapper.find(inputSelector).prop('defaultValue'), '');
  });

  it('clears the displayed grade value if the currently-focused student has an empty grade', async () => {
    const wrapper = renderForm();

    await waitForGradeFetch(wrapper);
    assert.strictEqual(wrapper.find(inputSelector).prop('defaultValue'), '10');

    fakeGradingService.fetchGrade.resolves({ currentScore: null });
    wrapper.setProps({ student: fakeStudentAlt });
    await waitForGradeFetch(wrapper);

    assert.strictEqual(wrapper.find(inputSelector).prop('defaultValue'), '');
  });

  it("displays a focused-student's grade if it is 0 (zero)", async () => {
    fakeGradingService.fetchGrade.resolves({ currentScore: 0 });
    const wrapper = renderForm();

    assert.strictEqual(wrapper.find(inputSelector).prop('defaultValue'), '');

    await waitForGradeFetch(wrapper);

    assert.strictEqual(wrapper.find(inputSelector).prop('defaultValue'), '0');
  });

  it('focuses the input field when changing students and fetching the grade', async () => {
    document.body.focus();
    const wrapper = renderForm();

    await waitForGradeFetch(wrapper);

    wrapper.setProps({ student: fakeStudentAlt });

    await waitForGradeFetch(wrapper);

    assert.equal(
      document.activeElement.getAttribute('data-testid'),
      'grade-input'
    );
  });

  it("selects the input field's text when changing students and fetching the grade", async () => {
    document.body.focus();
    const wrapper = renderForm();

    await waitForGradeFetch(wrapper);

    wrapper.setProps({ student: fakeStudentAlt });

    await waitForGradeFetch(wrapper);

    assert.equal(document.getSelection().toString(), '10');
  });

  context('validation messages', () => {
    beforeEach(() => {
      $imports.$mock({
        '../utils/validation': {
          validateGrade: sinon.stub().returns('err'),
        },
      });
    });

    it('does not render the validation message by default', () => {
      const wrapper = renderForm();
      assert.isFalse(wrapper.find('ValidationMessage').exists());
    });

    it('shows the validation message when the validator returns an error', () => {
      const wrapper = renderForm();
      wrapper.find('button[type="submit"]').simulate('click');
      assert.isTrue(wrapper.find('ValidationMessage').prop('open'));
      assert.equal(wrapper.find('ValidationMessage').prop('message'), 'err');

      // Clicking the error message should dismiss it.
      wrapper.find('ValidationMessage').invoke('onClose')();
      assert.isFalse(wrapper.find('ValidationMessage').prop('open'));
    });

    it('hides the validation message after it was opened when input is detected', () => {
      $imports.$mock({
        '../utils/validation': {
          validateGrade: sinon.stub().returns('err'),
        },
      });
      const wrapper = renderForm();
      wrapper.find('button[type="submit"]').simulate('click');
      wrapper.find(inputSelector).simulate('input');
      assert.isFalse(wrapper.find('ValidationMessage').prop('open'));
    });
  });

  context('when submitting a grade', () => {
    it('shows a loading spinner when submitting a grade', () => {
      const wrapper = renderForm();
      wrapper.find('button[type="submit"]').simulate('click');
      assert.isTrue(wrapper.find('FullScreenSpinner').exists());
    });

    it('shows the error dialog when the grade request throws an error', async () => {
      const wrapper = renderForm();
      const error = {
        serverMessage: 'message',
        details: 'details',
      };
      fakeGradingService.submitGrade.rejects(error);

      wrapper.find('button[type="submit"]').simulate('click');

      const errorModal = await waitForElement(wrapper, 'ErrorModal');
      // Ensure the error object passed to ErrorDialog is the same as the one thrown
      assert.equal(errorModal.prop('error'), error);

      // Error message should be hidden when its close action is triggered.
      wrapper.find('ErrorModal').invoke('onCancel')();
      assert.isFalse(wrapper.exists('ErrorModal'));
    });

    it('sets the success animation class when the grade has posted', async () => {
      const wrapper = renderForm();

      wrapper.find('button[type="submit"]').simulate('click');

      await waitForGradeFetch(wrapper);

      assert.isTrue(
        wrapper.find(inputSelector).hasClass('animate-gradeSubmitSuccess')
      );
    });

    it('removes the success animation class after keyboard input', async () => {
      const wrapper = renderForm();

      wrapper.find('button[type="submit"]').simulate('click');

      await waitForGradeFetch(wrapper);

      wrapper.find(inputSelector).simulate('input');
      assert.isFalse(
        wrapper.find(inputSelector).hasClass('animate-gradeSubmitSuccess')
      );
    });

    it('closes the spinner after the grade has posted', async () => {
      const wrapper = renderForm();
      wrapper.find('button[type="submit"]').simulate('click');

      await waitFor(() => {
        wrapper.update();
        return !wrapper.exists('FullScreenSpinner');
      });
    });
  });

  context('when fetching a grade', () => {
    it('sets the defaultValue prop to an empty string if the grade is falsey', async () => {
      fakeGradingService.fetchGrade.resolves({ currentScore: null });
      const wrapper = renderForm();

      await waitForGradeFetch(wrapper);

      assert.strictEqual(wrapper.find(inputSelector).prop('defaultValue'), '');
    });

    it('shows the error dialog when the grade request throws an error', async () => {
      const error = {
        serverMessage: 'message',
        details: 'details',
      };
      fakeGradingService.fetchGrade.rejects(error);
      const wrapper = renderForm();

      await waitForGradeFetch(wrapper);

      assert.isTrue(wrapper.find('ErrorModal').exists());
      // Ensure the error object passed to ErrorDialog is the same as the one thrown
      assert.equal(wrapper.find('ErrorModal').prop('error'), error);

      // Error message should be hidden when its close action is triggered.
      wrapper.find('ErrorModal').invoke('onCancel')();
      assert.isFalse(wrapper.exists('ErrorModal'));
    });

    it("sets the input defaultValue prop to the student's grade", async () => {
      const wrapper = renderForm();
      await waitForGradeFetch(wrapper);
      // note, grade is scaled by 10
      assert.strictEqual(
        wrapper.find(inputSelector).prop('defaultValue'),
        '10'
      );
    });

    it('sets hides the Spinner after the grade is fetched', async () => {
      const wrapper = renderForm();
      await waitForGradeFetch(wrapper);
      assert.isFalse(
        wrapper.find('.SubmitGradeForm__grade-wrapper').find('Spinner').exists()
      );
    });
  });

  it(
    'should pass a11y checks',
    checkAccessibility(
      {
        content: () => renderForm(),
      },
      {
        name: 'when disabled',
        content: () => renderForm({ disabled: true }),
      }
    )
  );
});
