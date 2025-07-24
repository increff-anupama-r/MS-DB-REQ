/// <reference types="cypress" />

describe('ArtifactFormChat Component', () => {
	beforeEach(() => {
		// Navigate to the chat interface and open the form
		cy.visit('/');
		cy.get('[data-testid="artifact-form-button"]').click();
		cy.get('[data-testid="artifact-form-chat"]').should('be.visible');
	});

	it('should complete normal flow successfully', () => {
		// Test data
		const testData = {
			title: 'Improve dashboard performance',
			type: 'Feature',
			client: 'Marketing Team',
			module: 'Analytics Dashboard',
			description: 'Optimize query performance and add caching',
			owner: 'Anupama',
			priority: 'High',
			due_date: 'next week'
		};

		// Fill all fields
		Object.entries(testData).forEach(([field, value]) => {
			cy.get('#artifact-form-input').type(value);
			cy.get('button[type="submit"]').click();
			cy.contains('Received:').should('be.visible');
		});

		// Submit the form
		cy.get('#artifact-form-input').type('submit');
		cy.get('button[type="submit"]').click();
		cy.contains('Submitting your request to Notion...').should('be.visible');
	});

	it('should handle edit functionality correctly', () => {
		// Fill all fields first
		const fields = [
			'Test Project',
			'Bug',
			'Test Client',
			'Test Module',
			'Test Description',
			'Anupama',
			'Medium',
			'tomorrow'
		];

		fields.forEach((field) => {
			cy.get('#artifact-form-input').type(field);
			cy.get('button[type="submit"]').click();
		});

		// Edit a field
		cy.get('#artifact-form-input').type('edit title');
		cy.get('button[type="submit"]').click();
		cy.contains('You are now editing: Title').should('be.visible');

		// Provide new value
		cy.get('#artifact-form-input').type('Updated Test Project');
		cy.get('button[type="submit"]').click();
		cy.contains('Received: Updated Test Project').should('be.visible');
	});

	it('should validate field inputs correctly', () => {
		// Test invalid type
		cy.get('#artifact-form-input').type('Valid Title');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('InvalidType');
		cy.get('button[type="submit"]').click();
		cy.contains('Please select a valid Type').should('be.visible');

		// Test valid type
		cy.get('#artifact-form-input').type('Feature');
		cy.get('button[type="submit"]').click();
		cy.contains('Received: Feature').should('be.visible');

		// Test invalid date
		cy.get('#artifact-form-input').type('Valid Client');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('Valid Module');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('Valid Description');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('Valid Owner');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('High');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('invalid date');
		cy.get('button[type="submit"]').click();
		cy.contains('Please enter a valid date').should('be.visible');
	});

	it('should handle fuzzy matching for typos', () => {
		// Test typo in type field
		cy.get('#artifact-form-input').type('Fuzzy Title');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('featur'); // Typo
		cy.get('button[type="submit"]').click();
		cy.contains('Received: Feature').should('be.visible'); // Should auto-correct

		// Test typo in priority field
		cy.get('#artifact-form-input').type('Fuzzy Client');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('Fuzzy Module');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('Fuzzy Description');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('Fuzzy Owner');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('hihg'); // Typo
		cy.get('button[type="submit"]').click();
		cy.contains('Received: High').should('be.visible'); // Should auto-correct
	});

	it('should parse various date formats correctly', () => {
		// Fill fields up to due date
		const fields = [
			'Date Test Title',
			'Bug',
			'Date Test Client',
			'Date Test Module',
			'Date Test Description',
			'Date Test Owner',
			'Critical'
		];

		fields.forEach((field) => {
			cy.get('#artifact-form-input').type(field);
			cy.get('button[type="submit"]').click();
		});

		// Test different date formats
		const dateTests = [
			{ input: 'today', expected: '2025-07-07' },
			{ input: 'tomorrow', expected: '2025-07-08' },
			{ input: 'next week', expected: '2025-07-14' },
			{ input: 'next month', expected: '2025-08-07' },
			{ input: 'in 5 days', expected: '2025-07-12' },
			{ input: '2025-12-25', expected: '2025-12-25' }
		];

		dateTests.forEach(({ input, expected }) => {
			cy.get('#artifact-form-input').type(input);
			cy.get('button[type="submit"]').click();
			cy.contains(`Received: ${expected}`).should('be.visible');
		});
	});

	it('should prevent submission with incomplete fields', () => {
		// Fill only first two fields
		cy.get('#artifact-form-input').type('Incomplete Title');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('Feature');
		cy.get('button[type="submit"]').click();

		// Try to submit
		cy.get('#artifact-form-input').type('submit');
		cy.get('button[type="submit"]').click();
		cy.contains('Cannot submit: Field Client is required').should('be.visible');
	});

	it('should handle cancel functionality', () => {
		cy.get('#artifact-form-input').type('Cancel Test Title');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('cancel');
		cy.get('button[type="submit"]').click();
		cy.contains('Request cancelled').should('be.visible');
	});

	it('should handle invalid edit field names', () => {
		// Fill all fields first
		const fields = [
			'Edit Test Title',
			'Feature',
			'Edit Test Client',
			'Edit Test Module',
			'Edit Test Description',
			'Edit Test Owner',
			'Medium',
			'2025-08-15'
		];

		fields.forEach((field) => {
			cy.get('#artifact-form-input').type(field);
			cy.get('button[type="submit"]').click();
		});

		// Try to edit non-existent field
		cy.get('#artifact-form-input').type('edit nonexistent');
		cy.get('button[type="submit"]').click();
		cy.contains('Field "nonexistent" not found').should('be.visible');
	});

	it('should handle attachment functionality', () => {
		// Test file upload
		cy.get('input[type="file"]').selectFile('cypress/fixtures/test-document.pdf');
		cy.contains('Added attachment(s): test-document.pdf').should('be.visible');

		// Test URL attachment
		cy.get('button[title="Add Attachment"]').click();
		cy.get('input[placeholder="Paste public URL..."]').type('https://example.com/document.pdf');
		cy.get('button').contains('Add URL').click();
		cy.contains('Added attachment URL: https://example.com/document.pdf').should('be.visible');

		// Verify attachments appear in tracker
		cy.get('.progress-tracker').within(() => {
			cy.contains('test-document.pdf').should('be.visible');
			cy.contains('https://example.com/document.pdf').should('be.visible');
		});
	});

	it('should update progress tracker in real-time', () => {
		// Check initial state
		cy.get('.progress-tracker').within(() => {
			cy.contains('0 of 8 fields completed').should('be.visible');
			cy.get('.progress-bar').should('have.css', 'width', '0%');
		});

		// Fill first field
		cy.get('#artifact-form-input').type('Progress Test Title');
		cy.get('button[type="submit"]').click();

		// Check progress updated
		cy.get('.progress-tracker').within(() => {
			cy.contains('1 of 8 fields completed').should('be.visible');
			cy.get('.progress-bar').should('not.have.css', 'width', '0%');
		});

		// Fill second field
		cy.get('#artifact-form-input').type('Feature');
		cy.get('button[type="submit"]').click();

		// Check progress updated again
		cy.get('.progress-tracker').within(() => {
			cy.contains('2 of 8 fields completed').should('be.visible');
		});
	});

	it('should highlight editing field in tracker', () => {
		// Fill all fields first
		const fields = [
			'Highlight Test Title',
			'Bug',
			'Highlight Test Client',
			'Highlight Test Module',
			'Highlight Test Description',
			'Highlight Test Owner',
			'Low',
			'2025-09-01'
		];

		fields.forEach((field) => {
			cy.get('#artifact-form-input').type(field);
			cy.get('button[type="submit"]').click();
		});

		// Edit a field
		cy.get('#artifact-form-input').type('edit title');
		cy.get('button[type="submit"]').click();

		// Check that the field is highlighted in tracker
		cy.get('.progress-tracker').within(() => {
			cy.get('.field-item').contains('Title').parent().should('have.class', 'editing');
			cy.contains('Editing').should('be.visible');
		});
	});

	it('should handle form reset correctly', () => {
		// Fill some fields
		cy.get('#artifact-form-input').type('Reset Test Title');
		cy.get('button[type="submit"]').click();
		cy.get('#artifact-form-input').type('Feature');
		cy.get('button[type="submit"]').click();

		// Reset the form
		cy.get('button[title="Reset Form"]').click();

		// Check that form is reset
		cy.get('.progress-tracker').within(() => {
			cy.contains('0 of 8 fields completed').should('be.visible');
		});
		cy.get('#artifact-form-input').should('have.value', '');
	});

	it('should handle submission errors gracefully', () => {
		// Mock a submission error
		cy.intercept('POST', '/api/notion/feature-request', {
			statusCode: 400,
			body: { error: 'Invalid due_date format' }
		}).as('submitRequest');

		// Fill all fields
		const fields = [
			'Error Test Title',
			'Feature',
			'Error Test Client',
			'Error Test Module',
			'Error Test Description',
			'Error Test Owner',
			'High',
			'2025-12-25'
		];

		fields.forEach((field) => {
			cy.get('#artifact-form-input').type(field);
			cy.get('button[type="submit"]').click();
		});

		// Submit and check error handling
		cy.get('#artifact-form-input').type('submit');
		cy.get('button[type="submit"]').click();
		cy.wait('@submitRequest');
		cy.contains('Submission failed: Invalid due_date format').should('be.visible');
		cy.contains('Please provide a valid value for Due Date').should('be.visible');
	});
});
