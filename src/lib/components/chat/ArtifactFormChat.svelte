<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { onMount, getContext, createEventDispatcher, tick } from 'svelte';
	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	import { chatId, settings, showArtifacts, showControls } from '$lib/stores';
	import { createMessagesList } from '$lib/utils';

	import XMark from '../icons/XMark.svelte';
	import ArrowLeft from '../icons/ArrowLeft.svelte';
	import Check from '../icons/Check.svelte';
	import Refresh from '../icons/ArrowPath.svelte';

	import { createFeatureRequest, getNameSuggestions, matchUserName } from '$lib/apis/notion';
	import dayjs from 'dayjs';
	import customParseFormat from 'dayjs/plugin/customParseFormat';
	import levenshtein from 'js-levenshtein';
	dayjs.extend(customParseFormat);

	export let overlay = false;
	export let history;
	export let submitPrompt: Function;
	export let stopResponse: Function;
	export let showMessage: Function;
	export let eventTarget: EventTarget;

	let messages = [];
	let formData = {
		title: '',
		type: '',
		client: '',
		module: '',
		description: '',
		owner: '',
		priority: '',
		due_date: '',
		reference_link: '',
		created_by: ''
	};

	let fieldStatus = {
		title: 'pending',
		type: 'pending',
		client: 'pending',
		module: 'pending',
		description: 'pending',
		owner: 'pending',
		priority: 'pending',
		due_date: 'pending',
		reference_link: 'pending',
		created_by: 'pending'
	};

	let currentField = 'title';
	let isProcessing = false;
	let userInput = '';
	let chatFlow = [];
	let state = 'asking'; // 'asking', 'editing', 'review', 'submitting', 'done'
	let loading = false;
	let errorMsg = '';
	let attachments: File[] = [];
	let attachmentUrls: string[] = [];
	let showAttachmentInput = false;
	let attachmentUrlInput = '';
	let chatContainer;
	let editingField = null;
	let lastSummary = '';
	let isWaitingForInput = false;
	let isSubmitting = false;
	let submissionAttempts = 0;
	let lastError = null;
	let attachmentUploadStatus = {};

	let forceSubmit = false;
	let userSentiment = 'neutral';
	let conversationContext = [];

	// Name suggestion functionality
	let nameSuggestions = [];
	let showingSuggestions = false;
	let suggestionField = null;
	let lastSuggestionInput = '';

	const fieldConfig = {
		title: { name: 'Request Title', icon: '📝', description: 'Clear, descriptive request name' },
		type: {
			name: 'Type',
			icon: '🏷️',
			description: 'Request type (Feature, Bug, Improvement)',
			options: ['Feature', 'Bug', 'Improvement']
		},
		client: {
			name: 'Client or Business Unit',
			icon: '👤',
			description: 'The client or business unit requesting this'
		},
		module: {
			name: 'Module',
			icon: '📦',
			description: 'Specific part of the system this relates to'
		},
		description: {
			name: 'Request Description',
			icon: '🖊️',
			description: 'A concise but complete explanation of the request'
		},
		owner: {
			name: 'Request Owner',
			icon: '🧑‍💼',
			description: 'Responsible person for this request'
		},
		priority: {
			name: 'Priority',
			icon: '⚡',
			description: 'How urgent is this request? (Critical, High, Medium, Low)',
			options: ['0 - Critical', '1 - High', '2 - Medium', '3 - Low']
		},
		due_date: { name: 'Due Date', icon: '📅', description: 'Expected completion or delivery date' },
		reference_link: {
			name: 'Reference Link',
			icon: '🔗',
			description: 'Optional URL or reference link (optional)'
		},
		created_by: {
			name: 'Created By',
			icon: '📝',
			description: 'Full name of the person creating this request (required)'
		}
	};

	const fieldOrder = [
		'title',
		'type',
		'description',
		'owner',
		'priority',
		'due_date',
		'reference_link',
		'created_by',
		'client',
		'module'
	];

	// 1. Update fieldStatus to support 'skipped' status
	const SKIP_WORDS = ['skip', 'none', 'n/a'];
	const REQUIRED_FIELDS = ['title', 'type', 'description', 'priority', 'owner', 'created_by'];
	const OPTIONAL_FIELDS = fieldOrder.filter(
		(f) => !REQUIRED_FIELDS.includes(f) && f !== 'attachments'
	);
	const ALL_FIELDS = [...REQUIRED_FIELDS, ...OPTIONAL_FIELDS];
	const TOTAL_FIELDS = 11; // 10 fields + attachments
	const SKIPPABLE_FIELDS = ['module', 'client'];
	// Fields that support multiple values
	const MULTI_FIELDS = ['client', 'owner', 'module', 'reference_link'];

	// Name suggestion fields
	const NAME_SUGGESTION_FIELDS = ['owner', 'created_by'];

	$: if (history) {
		messages = createMessagesList(history, history.currentId);
		processMessages();
	} else {
		messages = [];
	}

	// Reactive statement to update field status when form data changes
	$: if (formData) {
		updateFieldStatus();
	}

	// Enhanced reactive progress tracking that updates immediately
	$: completionPercentage = calculateProgress();

	// Update progress whenever any form data changes
	$: if (formData) {
		completionPercentage = calculateProgress();
	}

	// Update progress when field status changes
	$: if (fieldStatus) {
		completionPercentage = calculateProgress();
	}

	// Update progress when attachments change
	$: if (attachments || attachmentUrls) {
		completionPercentage = calculateProgress();
	}

	// Update progress when editing field changes
	$: if (editingField) {
		completionPercentage = calculateProgress();
	}

	// Reactive statement to ensure input is enabled when form is active
	$: if (state !== 'done' && !loading) {
		setTimeout(() => {
			const input = document.getElementById('artifact-form-input');
			if (input && input.disabled) {
				input.disabled = false;
			}
		}, 50);
	}

	// Remove automatic reactive trigger - only trigger on user input

	// Function to handle name suggestion input
	async function handleNameSuggestionInput() {
		const input = userInput.trim();

		// Only show suggestions for inputs with 2+ characters
		if (input.length < 2) {
			clearSuggestions();
			return;
		}

		// Debounce the API call
		if (lastSuggestionInput === input) {
			return;
		}

		lastSuggestionInput = input;

		try {
			const token = localStorage.token;
			// Allow suggestions even without token (using test endpoint)

			const response = await getNameSuggestions(token, {
				partial_name: input,
				limit: 5
			});

			if (response && response.suggestions && response.suggestions.length > 0) {
				nameSuggestions = response.suggestions;
				showingSuggestions = true;
				suggestionField = currentField;

				// Add suggestion message to chat with better formatting
				const suggestionText =
					'I found ' +
					response.suggestions.length +
					' matching names:\n\n' +
					response.suggestions.map((s, i) => i + 1 + '. ' + s.name + ' - ' + s.email).join('\n') +
					'\n\nPlease select a number (1-' +
					response.suggestions.length +
					') or type the exact full name if not listed.';

				// Remove any existing suggestion messages first
				chatFlow = chatFlow.filter(
					(msg) =>
						!(
							msg.role === 'assistant' &&
							msg.content.includes('I found') &&
							msg.content.includes('matching names')
						)
				);

				// Add new suggestion message
				chatFlow.push({ role: 'assistant', content: suggestionText });
				chatFlow = [...chatFlow];
				await tick();
				scrollToBottom();

				// Set waiting state to true so user can respond to suggestions
				isWaitingForInput = true;
			} else {
				// If no suggestions found, process the input normally
				await processFieldInput(currentField, input);
			}
		} catch (error) {
			console.error('Error getting name suggestions:', error);
			// If error occurs, process the input normally
			await processFieldInput(currentField, input);
		}
	}

	// Function to clear suggestions
	function clearSuggestions() {
		nameSuggestions = [];
		showingSuggestions = false;
		suggestionField = null;
		lastSuggestionInput = '';

		// Don't remove suggestion messages from chat - let them stay visible
		// They will be naturally replaced when new suggestions are shown
	}

	// Function to handle suggestion selection
	async function handleSuggestionSelection(selection: string) {
		const num = parseInt(selection);

		if (num >= 1 && num <= nameSuggestions.length) {
			const selectedSuggestion = nameSuggestions[num - 1];

			// Add user selection to chat
			chatFlow.push({ role: 'user', content: selection });
			chatFlow = [...chatFlow];

			// Clear suggestions
			clearSuggestions();

			// Acknowledge the selection
			chatFlow.push({
				role: 'assistant',
				content:
					'I\'ve recorded "' +
					selectedSuggestion.name +
					'" for ' +
					fieldConfig[currentField].name +
					'.'
			});
			chatFlow = [...chatFlow];
			await tick();
			scrollToBottom();

			// Process the selected name
			await processFieldInput(currentField, selectedSuggestion.name);
		} else {
			// User typed something else - validate it properly
			// Add user input to chat
			chatFlow.push({ role: 'user', content: selection });
			chatFlow = [...chatFlow];

			// Clear suggestions
			clearSuggestions();

			// First, try to match the name using the API
			try {
				const token = localStorage.token;
				const matchResponse = await matchUserName(token, { name: selection });

				if (matchResponse && matchResponse.found && matchResponse.user) {
					// Found a match - use the matched name
					const matchedName = matchResponse.user.name;

					chatFlow.push({
						role: 'assistant',
						content:
							'I\'ve recorded "' + matchedName + '" for ' + fieldConfig[currentField].name + '.'
					});
					chatFlow = [...chatFlow];
					await tick();
					scrollToBottom();

					await processFieldInput(currentField, matchedName);
					return;
				} else if (
					matchResponse &&
					matchResponse.suggestions &&
					matchResponse.suggestions.length > 0
				) {
					// No exact match but we have suggestions - show them
					nameSuggestions = matchResponse.suggestions;
					showingSuggestions = true;
					suggestionField = currentField;

					const suggestionText =
						'I couldn\'t find an exact match for "' +
						selection +
						'". Here are some suggestions:\n\n' +
						matchResponse.suggestions
							.map((s, i) => i + 1 + '. ' + s.name + ' - ' + s.email)
							.join('\n') +
						'\n\nPlease select a number (1-' +
						matchResponse.suggestions.length +
						') or type the exact full name if not listed.';

					chatFlow.push({ role: 'assistant', content: suggestionText });
					chatFlow = [...chatFlow];
					await tick();
					scrollToBottom();
					return;
				}
			} catch (error) {
				console.error('Error matching user name:', error);
			}

			// If no match found or API failed, validate the input using AI
			const aiValidation = await validateFieldWithAI(currentField, selection);

			if (aiValidation && !aiValidation.valid) {
				// AI validation failed - ask user to re-enter
				chatFlow.push({
					role: 'assistant',
					content:
						aiValidation.message +
						'\n\nPlease provide a valid ' +
						fieldConfig[currentField].name +
						'.'
				});
				chatFlow = [...chatFlow];
				await tick();
				scrollToBottom();
				return;
			}

			// If we get here, the input seems valid - acknowledge it
			chatFlow.push({
				role: 'assistant',
				content: 'I\'ve recorded "' + selection + '" for ' + fieldConfig[currentField].name + '.'
			});
			chatFlow = [...chatFlow];
			await tick();
			scrollToBottom();

			await processFieldInput(currentField, selection);
		}
	}

	// Function to move to next field after processing input
	async function moveToNextField(field: string) {
		// Add acknowledgment message
		const ack = fieldAcknowledgments[field] || 'Got it!';

		// Find next field
		const nextIdx = fieldOrder.indexOf(field) + 1;

		if (nextIdx < fieldOrder.length) {
			const nextField = fieldOrder[nextIdx];
			currentField = nextField;
			state = 'asking';

			let nextPrompt = '';
			if (nextField === 'title')
				nextPrompt =
					'What is the title of your DB request? Please provide a clear, descriptive name.';
			else if (nextField === 'type')
				nextPrompt =
					'What type of request is this? Options: ' + fieldConfig[nextField].options.join(', ');
			else if (nextField === 'client')
				nextPrompt = 'Who is the client or business unit requesting this?';
			else if (nextField === 'module')
				nextPrompt = 'Which module or specific part of the system does this relate to?';
			else if (nextField === 'description')
				nextPrompt =
					'Please describe the requirement in detail. Include specific details about what needs to be implemented or fixed. Minimum 15 characters.';
			else if (nextField === 'priority')
				nextPrompt =
					'What is the priority level? Enter 0 for Critical, 1 for High, 2 for Medium, or 3 for Low. You can also type the word (e.g., "critical").';
			else if (nextField === 'due_date')
				nextPrompt =
					'What is the expected completion or delivery date? (e.g., 2025-07-20 or "next week")';
			else if (nextField === 'reference_link')
				nextPrompt =
					'Do you have any reference links or URLs related to this request? (If not applicable, type "skip", "n/a", or "none")';
			else if (nextField === 'owner')
				nextPrompt =
					'Who will be the owner responsible for this request? (Type a name to see matching suggestions)';
			else if (nextField === 'created_by')
				nextPrompt = 'Who is creating this request? (Type a name to see matching suggestions)';

			// Add acknowledgment message first
			chatFlow.push({ role: 'assistant', content: ack });
			chatFlow = [...chatFlow];
			await tick();
			scrollToBottom();

			// Then add the next field prompt
			chatFlow.push({ role: 'assistant', content: nextPrompt });
			chatFlow = [...chatFlow];
			saveChatFlow();
			await tick();
			scrollToBottom();
			focusInput();
		} else {
			// No more fields, show summary
			await showSummary();
			focusInput();
		}
	}

	// Enhanced processFieldInput to handle suggestions
	async function processFieldInput(field: string, value: string) {
		// Clear suggestions when processing input
		clearSuggestions();

		// Check if this is a suggestion selection
		if (showingSuggestions && suggestionField === field) {
			const num = parseInt(value);
			if (num >= 1 && num <= nameSuggestions.length) {
				const selectedSuggestion = nameSuggestions[num - 1];
				value = selectedSuggestion.name;
			}
		}

		// Rest of the existing processFieldInput logic...
		const validation = validateField(field, value);

		if (typeof validation === 'string') {
			// Validation error
			chatFlow.push({ role: 'assistant', content: validation });
			chatFlow = [...chatFlow];
			await tick();
			scrollToBottom();

			// Clear editing mode if we were editing and validation failed
			if (editingField === field) {
				editingField = null;
			}
			return;
		}

		if (validation && validation.valid) {
			// Valid input
			formData[field] = validation.correctedValue;
			formData = { ...formData }; // Trigger reactivity
			fieldStatus[field] = 'completed';
			fieldStatus = { ...fieldStatus }; // Trigger reactivity

			// Clear editing mode if we were editing
			if (editingField === field) {
				editingField = null;
			}

			// Move to next field
			await moveToNextField(field);
		}
	}

	const processMessages = () => {
		messages.forEach((message) => {
			if (message?.role === 'user' && message?.content) {
				extractFieldData(message.content);
			}
		});
		updateFieldStatus();
	};

	const extractFieldData = (content: string) => {
		const lines = content.split('\n');
		lines.forEach((line) => {
			const trimmed = line.trim();
			if (trimmed.includes(':')) {
				const [key, value] = trimmed.split(':').map((s) => s.trim());
				const fieldKey = key.toLowerCase().replace(/\s+/g, '_');
				if (formData.hasOwnProperty(fieldKey) && value) {
					formData[fieldKey] = value;
					formData = { ...formData }; // Trigger reactivity
				}
			}
		});
	};

	// 2. Update fieldStatus to support 'skipped' and 'need_review' status
	const updateFieldStatus = () => {
		Object.keys(fieldStatus).forEach((field) => {
			const value = formData[field];

			// Handle special values from validation
			if (value === 'SKIPPED' || value === 'N/A' || value === 'skip' || value === 'na') {
				fieldStatus[field] = 'skipped';
			} else if (value === 'NEED_REVIEW') {
				fieldStatus[field] = 'need_review';
			} else if (value === 'TBD') {
				fieldStatus[field] = 'need_review';
			} else if (formData[field] && formData[field].trim() !== '') {
				// Check quality for critical fields - more lenient
				if (field === 'description' && formData[field].length < 15) {
					fieldStatus[field] = 'warning';
				} else if (
					field === 'description' &&
					formData[field].toLowerCase().includes('i dont know')
				) {
					fieldStatus[field] = 'warning';
				} else if (field === 'title' && formData[field].length < 5) {
					fieldStatus[field] = 'warning';
				} else {
					fieldStatus[field] = 'completed';
				}
			} else {
				fieldStatus[field] = 'pending';
			}
		});
		fieldStatus = { ...fieldStatus }; // Trigger reactivity
	};

	// 3. Update getStatusIcon and getStatusColor for skipped and need_review
	const getStatusIcon = (status: string) => {
		switch (status) {
			case 'completed':
				return Check;
			case 'skipped':
				return null; // Will show yellow dot
			case 'need_review':
				return null; // Will show yellow dot
			case 'warning':
				return null; // Will show warning dot instead
			case 'pending':
				return null;
			default:
				return XMark;
		}
	};
	const getStatusColor = (status: string) => {
		switch (status) {
			case 'completed':
				return 'text-green-500';
			case 'skipped':
				return 'text-yellow-500'; // Yellow for skipped fields
			case 'need_review':
				return 'text-yellow-500';
			case 'warning':
				return 'text-yellow-500';
			case 'pending':
				return 'text-gray-400'; // Gray for pending fields
			default:
				return 'text-red-500';
		}
	};

	const getStatusBgColor = (status: string) => {
		switch (status) {
			case 'completed':
				return 'bg-green-50 dark:bg-green-900/20';
			case 'skipped':
				return 'bg-yellow-50 dark:bg-yellow-900/20'; // Yellow background for skipped fields
			case 'warning':
				return 'bg-yellow-50 dark:bg-yellow-900/20';
			case 'need_review':
				return 'bg-yellow-50 dark:bg-yellow-900/20';
			case 'pending':
				return 'bg-gray-50 dark:bg-gray-900/20'; // Gray background for pending fields
			default:
				return 'bg-red-50 dark:bg-red-900/20';
		}
	};

	function focusInput() {
		setTimeout(() => {
			const input = document.getElementById('artifact-form-input');
			if (input) {
				input.focus();
				input.value = '';
				// Ensure the input is not disabled
				input.disabled = false;
			}
		}, 100); // Increased timeout to ensure DOM is ready
	}

	// Upload file to /api/files/ and return the public URL
	async function uploadFileToServer(file) {
		const formData = new FormData();
		formData.append('file', file);
		try {
			const res = await fetch('/api/v1/files/', {
				method: 'POST',
				headers: {
					Accept: 'application/json',
					authorization: 'Bearer ' + localStorage.token
				},
				body: formData
			});
			if (!res.ok) {
				const errorData = await res.json();
				throw new Error(errorData.detail || 'Upload failed');
			}
			const data = await res.json();
			// console.log('Upload response:', data);

			// The backend returns a FileModelResponse with id and path
			if (data?.id) {
				// Construct the public URL for the file
				return (
					'https://' +
					window.location.host +
					'/api/v1/files/' +
					data.id +
					'/content/' +
					encodeURIComponent(data.filename)
				);
			}
			throw new Error('No file ID returned');
		} catch (e) {
			console.error('File upload error:', e);
			throw e;
		}
	}

	// Update generatePublicUrl to actually upload the file
	async function generatePublicUrl(file) {
		return await uploadFileToServer(file);
	}

	// Update handleFileChange to show upload progress and use real URLs
	async function handleFileChange(event) {
		const files = Array.from(event.target.files);
		const validFiles = [];
		const invalidFiles = [];

		for (const file of files) {
			const validation = validateAttachment(file);
			if (validation.valid) {
				try {
					attachmentUploadStatus[file.name] = { status: 'uploading', message: 'Uploading...' };
					attachmentUploadStatus = { ...attachmentUploadStatus }; // Trigger reactivity

					const url = await uploadFileToServer(file);
					attachmentUploadStatus[file.name] = { status: 'success', message: 'File uploaded', url };
					attachmentUploadStatus = { ...attachmentUploadStatus }; // Trigger reactivity

					validFiles.push(file);
					// Store the URL for Notion
					attachmentUrls.push(url);
					attachmentUrls = [...attachmentUrls]; // Trigger reactivity
				} catch (e) {
					attachmentUploadStatus[file.name] = {
						status: 'error',
						message: 'Upload failed: ' + e.message
					};
					attachmentUploadStatus = { ...attachmentUploadStatus }; // Trigger reactivity
					invalidFiles.push({ file, error: e.message });
				}
			} else {
				invalidFiles.push({ file, error: validation.error });
				attachmentUploadStatus[file.name] = { status: 'error', message: validation.error };
				attachmentUploadStatus = { ...attachmentUploadStatus }; // Trigger reactivity
			}
		}

		if (validFiles.length > 0) {
			attachments.push(...validFiles);
			attachments = [...attachments]; // Trigger reactivity
			chatFlow.push({
				role: 'assistant',
				content:
					'Added ' +
					validFiles.length +
					' file(s): ' +
					validFiles.map((f) => f.name).join(', ') +
					'. These will be included in your submission.'
			});
			chatFlow.push({
				role: 'assistant',
				content:
					"Type 'done' to review your request, or add more attachments. You can also type 'no attachments' to proceed without files."
			});
		}

		if (invalidFiles.length > 0) {
			const errorMsg = invalidFiles
				.map(({ file, error }) => '[' + file.name + ']: ' + error)
				.join('\n');
			chatFlow.push({
				role: 'assistant',
				content: 'Could not add some files:\n' + errorMsg
			});
		}

		chatFlow = [...chatFlow];
		event.target.value = '';
		saveChatFlow();
		scrollToBottom();
	}

	function handleAddUrl() {
		if (attachmentUrlInput.trim()) {
			const validation = validateUrl(attachmentUrlInput.trim());
			if (validation.valid) {
				attachmentUrls.push(attachmentUrlInput.trim());
				chatFlow.push({
					role: 'assistant',
					content: '✅ Added attachment URL: ' + attachmentUrlInput.trim()
				});
				chatFlow.push({
					role: 'assistant',
					content:
						"Type 'done' to review your request, or add more attachments. You can also type 'no attachments' to proceed without files."
				});
				attachmentUrlInput = '';
			} else {
				chatFlow.push({
					role: 'assistant',
					content: '❌ ' + validation.error
				});
			}
			chatFlow = [...chatFlow];
			saveChatFlow();
			showAttachmentInput = false;
			scrollToBottom();
		}
	}

	function removeAttachment(idx) {
		attachments.splice(idx, 1);
		attachments = [...attachments];
		saveChatFlow();
	}

	function removeAttachmentUrl(idx) {
		attachmentUrls.splice(idx, 1);
		attachmentUrls = [...attachmentUrls];
		saveChatFlow();
	}

	function saveChatFlow() {
		localStorage.setItem('artifactFormChatFlow', JSON.stringify(chatFlow));
		localStorage.setItem('artifactFormData', JSON.stringify(formData));
		localStorage.setItem('artifactFormFieldStatus', JSON.stringify(fieldStatus));
		localStorage.setItem(
			'artifactFormAttachments',
			JSON.stringify(attachments.map((f) => ({ name: f.name, size: f.size, type: f.type })))
		);
		localStorage.setItem('artifactFormAttachmentUrls', JSON.stringify(attachmentUrls));
	}

	function loadChatFlow() {
		const flow = localStorage.getItem('artifactFormChatFlow');
		const data = localStorage.getItem('artifactFormData');
		const status = localStorage.getItem('artifactFormFieldStatus');
		const att = localStorage.getItem('artifactFormAttachments');
		const attUrls = localStorage.getItem('artifactFormAttachmentUrls');
		if (flow) chatFlow = JSON.parse(flow);
		if (data) formData = JSON.parse(data);
		if (status) fieldStatus = JSON.parse(status);
		if (att) attachments = [];
		if (attUrls) attachmentUrls = JSON.parse(attUrls);
	}

	function clearChatFlow() {
		localStorage.removeItem('artifactFormChatFlow');
		localStorage.removeItem('artifactFormData');
		localStorage.removeItem('artifactFormFieldStatus');
		localStorage.removeItem('artifactFormAttachments');
		localStorage.removeItem('artifactFormAttachmentUrls');
	}

	function scrollToBottom() {
		if (chatContainer) {
			setTimeout(() => {
				chatContainer.scrollTop = chatContainer.scrollHeight;
			}, 100);
		}
	}

	function parseDate(input) {
		const today = dayjs();
		const weekdays = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
		const lower = input.trim().toLowerCase();

		if (/^tomorrow$/.test(lower)) return today.add(1, 'day').format('YYYY-MM-DD');
		if (/^next week$/.test(lower)) {
			// Always return a date at least 1 day in the future
			let nextWeekDate = today.add(7, 'day');
			if (!nextWeekDate.isAfter(today, 'day')) {
				nextWeekDate = today.add(8, 'day');
			}
			return nextWeekDate.format('YYYY-MM-DD');
		}
		if (/^next month$/.test(lower)) return today.add(1, 'month').format('YYYY-MM-DD');
		if (/^today$/.test(lower)) return today.format('YYYY-MM-DD');
		if (/^in (\d+) days?$/.test(lower)) {
			const match = lower.match(/^in (\d+) days?$/);
			return today.add(parseInt(match[1]), 'day').format('YYYY-MM-DD');
		}
		// Handle 'next friday', 'next week next friday', etc.
		const nextWeekdayMatch = lower.match(
			/^(next week )?(next )?(sunday|monday|tuesday|wednesday|thursday|friday|saturday)$/
		);
		if (nextWeekdayMatch) {
			let weekday = nextWeekdayMatch[3];
			let base = today;
			if (lower.includes('next week')) base = base.add(7, 'day');
			const target = weekdays.indexOf(weekday);
			let daysToAdd = (target - base.day() + 7) % 7;
			if (daysToAdd === 0) daysToAdd = 7; // always next occurrence
			return base.add(daysToAdd, 'day').format('YYYY-MM-DD');
		}
		// Try parsing as date
		const parsed = dayjs(
			input,
			['YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY', 'MMM D, YYYY', 'MMMM D, YYYY'],
			true
		);
		if (parsed.isValid()) return parsed.format('YYYY-MM-DD');
		return null;
	}

	function fuzzyMatch(input, options) {
		const normalized = input.trim().toLowerCase();
		let best = options[0];
		let minDist = Infinity;

		// Handle multi-word inputs like "feature request"
		const inputWords = normalized.split(/\s+/);

		for (const opt of options) {
			const optLower = opt.toLowerCase();
			const optWords = optLower.split(/\s+/);

			// Check if any input word matches the option
			for (const inputWord of inputWords) {
				const dist = levenshtein(inputWord, optLower);
				if (dist < minDist) {
					minDist = dist;
					best = opt;
				}
			}

			// Also check the full input against the option
			const fullDist = levenshtein(normalized, optLower);
			if (fullDist < minDist) {
				minDist = fullDist;
				best = opt;
			}
		}

		// More lenient matching for common phrases
		if (normalized.includes('feature') || normalized.includes('featurerequest')) {
			return 'Feature';
		}
		if (normalized.includes('bug') || normalized.includes('issue')) {
			return 'Bug';
		}
		if (normalized.includes('improve') || normalized.includes('enhance')) {
			return 'Improvement';
		}

		// More lenient matching: accept if close enough (2 typos for short, 3 for longer)
		if ((normalized.length <= 6 && minDist <= 2) || minDist <= 3) return best;
		return null;
	}

	// Security and validation functions
	function sanitizeInput(input) {
		// Remove potentially dangerous characters and scripts
		const dangerousPatterns = [
			/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
			/javascript:/gi,
			/on\w+\s*=/gi,
			/1\s+OR\s+1\s*=\s*1/gi,
			/UNION\s+SELECT/gi,
			/DROP\s+TABLE/gi,
			/INSERT\s+INTO/gi,
			/DELETE\s+FROM/gi,
			/UPDATE\s+SET/gi
		];

		let sanitized = input;
		dangerousPatterns.forEach((pattern) => {
			sanitized = sanitized.replace(pattern, '');
		});

		// Remove HTML tags
		sanitized = sanitized.replace(/<[^>]*>/g, '');

		// Remove excessive special characters
		sanitized = sanitized.replace(/[<>\"'&]/g, '');

		return sanitized.trim();
	}

	function isInputSafe(input) {
		const dangerousPatterns = [
			/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/i,
			/javascript:/i,
			/on\w+\s*=/i,
			/1\s+OR\s+1\s*=\s*1/i,
			/UNION\s+SELECT/i,
			/DROP\s+TABLE/i,
			/INSERT\s+INTO/i,
			/DELETE\s+FROM/i,
			/UPDATE\s+SET/i
		];

		return !dangerousPatterns.some((pattern) => pattern.test(input));
	}

	// Enhanced field validation with better description validation
	function validateField(field, value) {
		const sanitizedValue = typeof value === 'string' ? value.trim() : value;
		if (isFieldRequired(field)) {
			if (
				SKIP_WORDS.includes(sanitizedValue.toLowerCase()) ||
				sanitizedValue.toLowerCase() === 'n/a' ||
				sanitizedValue.toLowerCase() === 'na'
			) {
				return (
					'The ' +
					fieldConfig[field]?.name +
					' field is required and cannot be skipped or set to N/A. Please provide a valid value.'
				);
			}
		}
		if (field === 'title') {
			// Block skip/n/a responses for title (required field)
			const VAGUE_RESPONSES = [
				'skip',
				'n/a',
				'none',
				'i dont know',
				'idk',
				'not sure',
				'maybe',
				'tbd',
				'unknown'
			];
			if (VAGUE_RESPONSES.includes(sanitizedValue.toLowerCase())) {
				return 'Please provide a clear, descriptive request  title. Responses like "skip", "n/a", "i dont know" are not allowed for the title field.';
			}
			if (sanitizedValue.length < 3) {
				return 'Please provide a more descriptive title (at least 3 characters).';
			}
			// Check for excessive length (more than 100 characters)
			if (sanitizedValue.length > 100) {
				return 'Please provide a shorter title (maximum 100 characters).';
			}
			// Check for only emojis or special characters
			if (
				/^[🔥🛒🎉✨🎊🎈🎁🎂🎄🎃🎪🎭🎨🎬🎤🎧🎼🎹🎸🎻🎺🎷🥁🎮🎲🎯🎳🎰🎪🎭🎨🎬🎤🎧🎼🎹🎸🎻🎺🎷🥁🎮🎲🎯🎳🎰]+$/.test(
					sanitizedValue
				)
			) {
				return 'Please provide a descriptive title with text, not just emojis.';
			}
			// Check for repeated characters (like "aaaaaaaaaa")
			if (/^(.)\1{9,}$/.test(sanitizedValue)) {
				return 'Please provide a clear, descriptive request title (max 100 characters). Avoid special characters or placeholder text.';
			}
			return { valid: true, correctedValue: sanitizedValue };
		}

		if (field === 'type') {
			const validOptions = fieldConfig[field].options.map((opt) => opt.toLowerCase());
			const normalizedInput = sanitizedValue.trim().toLowerCase();
			const VAGUE_RESPONSES = [
				'skip',
				'n/a',
				'none',
				'i dont know',
				'idk',
				'not sure',
				'maybe',
				'tbd',
				'unknown'
			];
			if (VAGUE_RESPONSES.includes(normalizedInput)) {
				return (
					'Please select a valid type: ' +
					fieldConfig[field].options.join(', ') +
					'. Responses like "skip", "n/a", "i dont know" are not allowed.'
				);
			}

			// Check exact matches first (case-sensitive)
			if (fieldConfig[field].options.includes(sanitizedValue)) {
				return { valid: true, correctedValue: sanitizedValue };
			}

			// Check case-insensitive matches
			if (validOptions.includes(normalizedInput)) {
				return {
					valid: true,
					correctedValue: fieldConfig[field].options[validOptions.indexOf(normalizedInput)]
				};
			}

			return 'Please select a valid type: ' + fieldConfig[field].options.join(', ') + '.';
		}

		if (field === 'client') {
			// Allow skip/n/a for client field (skippable)
			if (
				sanitizedValue.trim().toLowerCase() === 'skip' ||
				sanitizedValue.toLowerCase() === 'n/a' ||
				sanitizedValue.toLowerCase() === 'na'
			) {
				return { valid: true, correctedValue: 'TBD' };
			}

			if (sanitizedValue.length < 2) {
				return 'Could you please provide a valid client or business unit name?';
			}

			// Check for HTML tags
			if (sanitizedValue.includes('<') || sanitizedValue.includes('>')) {
				return 'Please provide a valid client or business unit name without HTML tags.';
			}

			// Check for only special characters or numbers
			if (/^[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?0-9]+$/.test(sanitizedValue)) {
				return 'Please specify the client or business unit requesting this. It helps with ownership and tracking.';
			}

			return { valid: true, correctedValue: sanitizedValue };
		}

		if (field === 'module') {
			// Allow skip/n/a for module field (skippable)
			if (
				sanitizedValue.trim().toLowerCase() === 'skip' ||
				sanitizedValue.toLowerCase() === 'n/a' ||
				sanitizedValue.toLowerCase() === 'na'
			) {
				return { valid: true, correctedValue: 'TBD' };
			}

			if (sanitizedValue.length < 2) {
				return 'Could you please specify which module this relates to?';
			}

			// Check for camelCase (UserMgmt should be rejected)
			if (/^[A-Z][a-z]+[A-Z][a-z]+$/.test(sanitizedValue)) {
				return 'Please provide a module name in a readable format (e.g., "User Management" instead of "UserMgmt").';
			}

			// Check for vague responses
			const vagueResponses = ['i dont know', 'idk', 'not sure', 'maybe', 'same'];
			if (vagueResponses.includes(sanitizedValue.toLowerCase())) {
				return 'Please enter a valid system module or feature this request relates to (e.g., login, reports).';
			}

			// Check for only special characters
			if (/^[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+$/.test(sanitizedValue)) {
				return 'Please enter a valid system module or feature this request relates to (e.g., login, reports).';
			}

			return { valid: true, correctedValue: sanitizedValue };
		}

		if (field === 'description') {
			// Block skip/n/a responses for description (required field)
			const VAGUE_RESPONSES = [
				'skip',
				'n/a',
				'none',
				'i dont know',
				'idk',
				'not sure',
				'maybe',
				'tbd',
				'unknown'
			];
			if (VAGUE_RESPONSES.includes(sanitizedValue.toLowerCase())) {
				return 'Please provide a detailed description of the request. Responses like "skip", "n/a", "i dont know" are not allowed for the description field.';
			}

			// Check for XSS attempts
			if (sanitizedValue.includes('<script>') || sanitizedValue.includes('javascript:')) {
				return 'Please provide a valid description without script tags or JavaScript.';
			}

			if (sanitizedValue.length < 15) {
				return 'Please describe the requirement in detail (at least 15 characters).';
			}

			// Check for vague responses and gibberish
			const vagueResponses = [
				'test',
				'fix this',
				'hello',
				'same',
				'ok',
				'asdf',
				'qwerty',
				'123456',
				'abc'
			];
			if (vagueResponses.includes(sanitizedValue.toLowerCase())) {
				return 'Please provide a meaningful description that explains what you need and why. Avoid placeholder text or gibberish.';
			}

			// Check for repeated characters or patterns (gibberish detection)
			if (
				/^(.)\1{5,}$/.test(sanitizedValue) ||
				/^[a-z]{1,3}\s*[a-z]{1,3}\s*[a-z]{1,3}$/i.test(sanitizedValue)
			) {
				return 'Please provide a meaningful description that explains what you need and why. Avoid repeated characters or meaningless text.';
			}

			// Check if it's too generic
			if (
				sanitizedValue.toLowerCase().includes('the team requires') &&
				sanitizedValue.length < 30
			) {
				return 'Please provide more specific details about what the team needs and why. Be more descriptive.';
			}

			return { valid: true, correctedValue: sanitizedValue };
		}

		if (field === 'owner') {
			// Handle vague responses for owner field
			const VAGUE_RESPONSES = [
				'skip',
				'n/a',
				'none',
				'i dont know',
				'idk',
				'not sure',
				'maybe',
				'tbd',
				'unknown',
				'test',
				'hello',
				'ok',
				'same',
				'asdf',
				'qwerty',
				'123456',
				'abc'
			];
			if (VAGUE_RESPONSES.includes(sanitizedValue.toLowerCase())) {
				return 'Please provide the full name of the person responsible for this request. Responses like "skip", "n/a", "i dont know" are not allowed for the owner field.';
			}

			if (!sanitizedValue || sanitizedValue.length < 2) {
				return 'Please provide the full name of the person responsible (at least 2 characters).';
			}

			// Check for only special characters or numbers
			if (/^[0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+$/.test(sanitizedValue)) {
				return 'Please provide a valid name, not just numbers or special characters.';
			}

			// Block single random letters
			if (/^[a-zA-Z]$/.test(sanitizedValue)) {
				return 'Please provide the full name of the person responsible, not just a single letter.';
			}

			// Check for patterns that look like partial names or typos (like "din1")
			if (/^[a-z]{1,3}[0-9]+$/i.test(sanitizedValue)) {
				return 'This looks like a partial name with numbers. Please provide the complete name of the person responsible.';
			}

			// Clean up the name
			let ownerValue = sanitizedValue;
			ownerValue = ownerValue.replace(
				/^(i think|maybe|probably|it'?s|it is|umm|perhaps|possibly|likely|the owner is|the creator is|owner is|responsible person is)\s+/i,
				''
			);
			ownerValue = ownerValue.trim();

			if (ownerValue.split(' ').length === 1) {
				ownerValue = ownerValue.charAt(0).toUpperCase() + ownerValue.slice(1).toLowerCase();
			} else {
				ownerValue = ownerValue
					.split(' ')
					.map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
					.join(' ');
			}

			return { valid: true, correctedValue: ownerValue };
		}

		if (field === 'priority') {
			// Block skip/n/a responses for priority (required field)
			const VAGUE_RESPONSES = [
				'skip',
				'n/a',
				'none',
				'i dont know',
				'idk',
				'not sure',
				'maybe',
				'tbd',
				'unknown'
			];
			if (VAGUE_RESPONSES.includes(sanitizedValue.toLowerCase())) {
				return 'Please select a valid priority level. Responses like "skip", "n/a", "i dont know" are not allowed for the priority field.';
			}

			// Enhanced mapping for priority
			const priorityMap = {
				'0': '0 - Critical',
				critical: '0 - Critical',
				'0 - critical': '0 - Critical',
				urgent: '0 - Critical',
				'1': '1 - High',
				high: '1 - High',
				'1 - high': '1 - High',
				important: '1 - High',
				'2': '2 - Medium',
				medium: '2 - Medium',
				'2 - medium': '2 - Medium',
				normal: '2 - Medium',
				standard: '2 - Medium',
				'3': '3 - Low',
				low: '3 - Low',
				'3 - low': '3 - Low',
				'nice to have': '3 - Low',
				optional: '3 - Low'
			};

			const normalized = sanitizedValue.toLowerCase();
			if (priorityMap[normalized] !== undefined) {
				return { valid: true, correctedValue: priorityMap[normalized] };
			}

			// Accept number input (as number type)
			if (!isNaN(sanitizedValue) && priorityMap[sanitizedValue] !== undefined) {
				return { valid: true, correctedValue: priorityMap[sanitizedValue] };
			}

			return 'Please select a valid priority:\n• 0 or "Critical" (urgent, blocking work)\n• 1 or "High" (important, needs attention soon)\n• 2 or "Medium" (normal priority)\n• 3 or "Low" (nice to have, not urgent)';
		}

		if (field === 'due_date') {
			if (sanitizedValue.trim().toLowerCase() === 'yesterday') {
				return 'Due date cannot be in the past. Please enter a future date.';
			}

			// Try natural language parsing first
			let parsed = parseDate(sanitizedValue);

			// If natural language parsing fails, try YYYY-MM-DD format
			if (!parsed && /^\d{4}-\d{2}-\d{2}$/.test(sanitizedValue)) {
				parsed = sanitizedValue;
			}

			// Try DD/MM/YYYY format as fallback
			if (!parsed && /^(\d{2})\/(\d{2})\/(\d{4})$/.test(sanitizedValue)) {
				const [_, d, m, y] = sanitizedValue.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
				parsed = dayjs('' + y + '-' + m + '-' + d).isValid()
					? dayjs('' + y + '-' + m + '-' + d).format('YYYY-MM-DD')
					: null;
			}

			if (!parsed) {
				return 'Please enter a valid date (YYYY-MM-DD) or use phrases like "tomorrow", "next week", "friday", etc.';
			}

			// Reject invalid dates like 2025-13-45
			if (!dayjs(parsed, 'YYYY-MM-DD', true).isValid()) {
				return 'Please enter a valid date (YYYY-MM-DD) or use phrases like "tomorrow", "next week".';
			}

			// Reject past dates
			if (dayjs(parsed).isBefore(dayjs(), 'day')) {
				return 'Due date cannot be in the past. Please enter a future date.';
			}

			return { valid: true, correctedValue: parsed };
		}

		if (field === 'reference_link') {
			// Handle remove/n/a for reference link
			if (
				!sanitizedValue ||
				SKIP_WORDS.includes(sanitizedValue.toLowerCase()) ||
				sanitizedValue.toLowerCase() === 'remove' ||
				sanitizedValue.toLowerCase() === 'delete' ||
				sanitizedValue.toLowerCase() === 'clear' ||
				sanitizedValue.toLowerCase() === 'none'
			) {
				return { valid: true, correctedValue: '' };
			}

			// Check for valid URL format
			const startsWithHttp =
				sanitizedValue.startsWith('http://') || sanitizedValue.startsWith('https://');
			const hasDot = sanitizedValue.includes('.') && sanitizedValue.indexOf('.') > 0;
			const hasNoSpaces = !sanitizedValue.includes(' ');
			const noJavaScript = !sanitizedValue.toLowerCase().includes('javascript:');

			if (!startsWithHttp || !hasDot || !hasNoSpaces || !noJavaScript) {
				return 'Please provide a valid URL that starts with http:// or https://, contains at least one dot (.), has no spaces, and no JavaScript.';
			}

			// Check for private Gmail links
			if (
				sanitizedValue.toLowerCase().includes('mail.google.com') ||
				sanitizedValue.toLowerCase().includes('gmail.com')
			) {
				return "This appears to be a private Gmail link. Please ensure it's a publicly accessible URL or internal document link.";
			}

			// Check for other private email links
			if (
				sanitizedValue.toLowerCase().includes('outlook.com') ||
				sanitizedValue.toLowerCase().includes('yahoo.com') ||
				sanitizedValue.toLowerCase().includes('hotmail.com')
			) {
				return 'This appears to be a private email link. Please provide a publicly accessible URL or internal document link.';
			}

			return { valid: true, correctedValue: sanitizedValue };
		}

		if (field === 'created_by') {
			const VAGUE_RESPONSES = [
				'skip',
				'n/a',
				'none',
				'i dont know',
				'idk',
				'not sure',
				'maybe',
				'tbd',
				'unknown',
				'test',
				'hello',
				'ok',
				'same',
				'asdf',
				'qwerty',
				'123456',
				'abc'
			];
			if (VAGUE_RESPONSES.includes(sanitizedValue.toLowerCase())) {
				return 'Please provide your full name. Responses like "skip", "n/a", "i dont know" are not allowed for this field.';
			}
			if (!sanitizedValue || sanitizedValue.length < 2) {
				return 'Please provide your full name (at least 2 characters).';
			}
			if (/^[0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+$/.test(sanitizedValue)) {
				return 'Please provide a valid name, not just numbers or special characters.';
			}
			// Block single random letters
			if (/^[a-zA-Z]$/.test(sanitizedValue)) {
				return 'Please provide your full name, not just a single letter.';
			}
			// Check for patterns that look like partial names or typos (like "din1")
			if (/^[a-z]{1,3}[0-9]+$/i.test(sanitizedValue)) {
				return 'This looks like a partial name with numbers. Please provide your complete name.';
			}
			return { valid: true, correctedValue: sanitizedValue };
		}

		if (MULTI_FIELDS.includes(field)) {
			// Accept comma-separated values, trim each, filter out empty
			const values = sanitizedValue
				.split(',')
				.map((v) => v.trim())
				.filter(Boolean);
			if (values.length === 0) {
				return 'Please provide at least one value for ' + fieldConfig[field].name + '.';
			}
			// Validate each value
			const validated = values.map((val) => {
				if (field === 'reference_link') {
					if (
						!val ||
						SKIP_WORDS.includes(val.toLowerCase()) ||
						val.toLowerCase() === 'remove' ||
						val.toLowerCase() === 'delete' ||
						val.toLowerCase() === 'clear' ||
						val.toLowerCase() === 'none'
					) {
						return '';
					}
					const startsWithHttp = val.startsWith('http://') || val.startsWith('https://');
					const hasDot = val.includes('.') && val.indexOf('.') > 0;
					const hasNoSpaces = !val.includes(' ');
					const noJavaScript = !val.toLowerCase().includes('javascript:');
					if (!startsWithHttp || !hasDot || !hasNoSpaces || !noJavaScript) {
						return null;
					}
					return val;
				} else {
					if (!val || val.length < 2) return null;
					if (/^[0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+$/.test(val)) return null;
					if (/^[a-zA-Z]$/.test(val)) return null;
					return val;
				}
			});
			if (validated.includes(null)) {
				return (
					'One or more values for ' +
					fieldConfig[field].name +
					' are invalid. Please check your input.'
				);
			}
			return { valid: true, correctedValue: validated.filter((v) => v !== '') };
		}

		return { valid: true, correctedValue: sanitizedValue };
	}

	// Detect vague inputs that need guidance instead of processing as field data
	async function detectVagueInput(userInput, currentField) {
		const lowerInput = userInput.toLowerCase().trim();

		// Patterns that indicate the user is asking for help or guidance
		const vaguePatterns = [
			// Help-seeking patterns
			/how to fill/i,
			/how do i fill/i,
			/what should i fill/i,
			/what do i need to fill/i,
			/now what/i,
			/what next/i,
			/what should i do/i,
			/i don't know/i,
			/i dont know/i,
			/idk/i,
			/not sure/i,
			/maybe/i,
			/perhaps/i,
			/um/i,
			/umm/i,
			/uh/i,
			/uhh/i,

			// Question patterns
			/\?$/,
			/what is/i,
			/can you help/i,
			/help me/i,
			/i need help/i,
			/please help/i,

			// Confusion patterns
			/i'm confused/i,
			/im confused/i,
			/confused/i,
			/not clear/i,
			/unclear/i,
			/what does this mean/i,

			// Generic responses
			/ok/i,
			/okay/i,
			/sure/i,
			/fine/i,
			/whatever/i,
			/same/i,
			/yes/i,
			/no/i,

			// Very short or unclear inputs
			/^[a-z]{1,2}$/i,
			/^[0-9]{1,2}$/,
			/^[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+$/,

			// Test inputs
			/test/i,
			/hello/i,
			/hi/i,
			/bye/i,
			/asdf/i,
			/qwerty/i,
			/123456/i,
			/abc/i
		];

		// Check if input matches any vague patterns
		for (const pattern of vaguePatterns) {
			if (pattern.test(lowerInput)) {
				return true;
			}
		}

		// Check for very short inputs that might be incomplete
		if (lowerInput.length < 3 && !/^(0|1|2|3|critical|high|medium|low)$/i.test(lowerInput)) {
			return true;
		}

		// Use AI to make final determination for complex cases
		try {
			const systemPrompt = `You are an expert at detecting whether user input is a vague request for help or actual field data.

Current field: ${currentField}
Field description: ${fieldConfig[currentField]?.description || 'No description available'}

User input: "${userInput}"

Determine if this input is:
1. A vague request for help/guidance (should be rejected)
2. Actual data for the field (should be processed)

Vague inputs include:
- Questions about how to fill the field
- Requests for help or clarification
- Generic responses like "ok", "same", "test"
- Confusion expressions like "i don't know", "not sure"
- Very short or unclear inputs

Respond with JSON:
{
  "isVague": true/false,
  "reason": "explanation of why it's vague or valid",
  "confidence": 0.0-1.0
}`;

			const response = await callOpenAI([
				{ role: 'system', content: systemPrompt },
				{ role: 'user', content: `Analyze this input for field "${currentField}": "${userInput}"` }
			]);

			if (response) {
				const result = JSON.parse(response);
				return result.isVague;
			}
		} catch (error) {
			console.error('Error in AI vague input detection:', error);
		}

		return false;
	}

	// Provide AI-powered guidance for vague inputs
	async function provideAIGuidance(userInput, currentField) {
		const fieldInfo = fieldConfig[currentField];

		try {
			const systemPrompt = `You are a helpful AI assistant guiding users through a database request form. The user has provided a vague input and needs guidance.

Current field: ${currentField}
Field name: ${fieldInfo?.name || currentField}
Field description: ${fieldInfo?.description || 'No description available'}

User's vague input: "${userInput}"

Provide helpful, encouraging guidance that:
1. Acknowledges their confusion or question
2. Explains what information is needed for this specific field
3. Gives clear examples of what they can provide
4. Encourages them to provide the actual information
5. Keeps the tone friendly and supportive

Make your response conversational and specific to the field. Don't be too long - keep it concise but helpful.`;

			const response = await callOpenAI([
				{ role: 'system', content: systemPrompt },
				{
					role: 'user',
					content: `Help the user with field "${currentField}" after their input: "${userInput}"`
				}
			]);

			if (response) {
				return response;
			}
		} catch (error) {
			console.error('Error in AI guidance generation:', error);
		}

		// Fallback guidance
		return `I understand you might be unsure about the ${fieldInfo?.name || currentField} field. 

For this field, I need: ${fieldInfo?.description || 'specific information'}

Could you please provide the actual ${fieldInfo?.name || currentField} information? For example, if this is a name field, provide the actual name. If it's a date field, provide the actual date.

I'm here to help guide you through each field!`;
	}

	// AI-powered field validation
	async function validateFieldWithAI(field, value) {
		// Special handling for name fields (owner, created_by)
		if (field === 'owner' || field === 'created_by') {
			const sanitizedValue = typeof value === 'string' ? value.trim() : value;

			// Check for invalid patterns
			if (/^[0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+$/.test(sanitizedValue)) {
				return {
					valid: false,
					message: 'Please provide a valid name, not just numbers or special characters.',
					suggestion: 'Enter a real person\'s name (e.g., "John Smith", "Maria Garcia")'
				};
			}

			// Check for single letters or very short inputs
			if (/^[a-zA-Z]$/.test(sanitizedValue) || sanitizedValue.length < 2) {
				return {
					valid: false,
					message: 'Please provide a full name, not just a single letter or very short input.',
					suggestion: 'Enter a complete name (e.g., "John Smith", "Maria Garcia")'
				};
			}

			// Check for patterns that look like partial names or typos
			if (/^[a-z]{1,3}[0-9]+$/i.test(sanitizedValue)) {
				return {
					valid: false,
					message: 'This looks like a partial name with numbers. Please provide a complete name.',
					suggestion: 'Enter the full name of the person (e.g., "John Smith", "Maria Garcia")'
				};
			}

			// Check for vague responses
			const vagueResponses = [
				'skip',
				'n/a',
				'none',
				'i dont know',
				'idk',
				'not sure',
				'maybe',
				'tbd',
				'unknown',
				'test',
				'hello',
				'ok',
				'same',
				'asdf',
				'qwerty',
				'123456',
				'abc'
			];
			if (vagueResponses.includes(sanitizedValue.toLowerCase())) {
				return {
					valid: false,
					message:
						'Please provide a real person\'s name. Responses like "' +
						sanitizedValue +
						'" are not allowed.',
					suggestion: 'Enter the actual name of the person (e.g., "John Smith", "Maria Garcia")'
				};
			}

			// If it passes basic checks, it's likely valid
			return {
				valid: true,
				message: '',
				suggestion: ''
			};
		}

		const systemPrompt =
			"You are a validation expert. Analyze the given value for the specified field and determine if it's appropriate.\n" +
			'Field: ' +
			field +
			'\n' +
			'Value: "' +
			value +
			'"\n' +
			'\n' +
			'Validation criteria:\n' +
			'- Title: Should be descriptive, professional, 3+ characters, not just emojis or numbers\n' +
			'- Module: Should be readable (not camelCase like "UserMgmt"), 2+ characters\n' +
			'- Owner: Should be a real name, not just numbers or special characters, 2+ characters\n' +
			'- Created By: Should be a real name, not just numbers or special characters, 2+ characters\n' +
			'\n' +
			'Respond in JSON format:\n' +
			'{\n' +
			'  "valid": true/false,\n' +
			'  "message": "explanation if invalid",\n' +
			'  "suggestion": "helpful suggestion if invalid"\n' +
			'}';

		try {
			const response = await callOpenAI([
				{ role: 'system', content: systemPrompt },
				{ role: 'user', content: 'Validate "' + value + '" for field "' + field + '"' }
			]);

			if (response) {
				const result = JSON.parse(response);
				if (!result.valid) {
					return {
						field: field,
						extracted_value: value,
						confidence: 0.8,
						validation: 'invalid',
						message: result.message,
						suggestion: result.suggestion
					};
				}
			}
		} catch (error) {
			console.error('AI validation error:', error);
		}

		return null; // Let regular validation handle it
	}

	// Enhanced progress calculation that considers quality, validation errors, and skipped fields
	function calculateProgress() {
		const completedFields = ALL_FIELDS.filter((f) => fieldStatus[f] === 'completed').length;
		const skippedFields = ALL_FIELDS.filter((f) => fieldStatus[f] === 'skipped').length;
		const needReviewFields = ALL_FIELDS.filter((f) => fieldStatus[f] === 'need_review').length;
		const warningFields = ALL_FIELDS.filter((f) => fieldStatus[f] === 'warning').length;
		const attachmentBonus = attachments.length > 0 || attachmentUrls.length > 0 ? 1 : 0;

		// Don't count fields with warnings or need review as fully complete
		const validCompletedFields = completedFields - warningFields;

		// Don't count skipped fields in progress - they don't contribute to completion
		const totalCompleted = validCompletedFields + attachmentBonus;
		const cappedCompleted = Math.min(totalCompleted, TOTAL_FIELDS);

		// If there are validation errors or skipped fields, cap at 95% to indicate issues
		if (warningFields > 0 || needReviewFields > 0 || skippedFields > 0) {
			return Math.min(Math.round((cappedCompleted / TOTAL_FIELDS) * 100), 95);
		}

		return Math.round((cappedCompleted / TOTAL_FIELDS) * 100);
	}

	// Session persistence disabled for privacy
	// No data is stored locally or persisted between sessions

	// Named Entity Recognition (NER) functions
	function extractEntities(text) {
		const entities = {
			names: [],
			dates: [],
			priorities: [],
			modules: [],
			urls: [],
			emails: []
		};

		// Extract names (2+ words with capital letters)
		const namePattern = /\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b/g;
		const names = text.match(namePattern);
		if (names) {
			entities.names = names.filter((name) => name.length > 3);
		}

		// Extract dates
		const datePatterns = [
			/\b(today|tomorrow|yesterday|next week|last week|next month|last month)\b/gi,
			/\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/gi,
			/\b(january|february|march|april|may|june|july|august|september|october|november|december)\b/gi,
			/\b\d{1,2}\/\d{1,2}\/\d{4}\b/g,
			/\b\d{4}-\d{2}-\d{2}\b/g,
			/\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/gi,
			/\bthis\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/gi
		];

		datePatterns.forEach((pattern) => {
			const matches = text.match(pattern);
			if (matches) {
				entities.dates.push(...matches);
			}
		});

		// Extract priorities
		const priorityPatterns = [
			/\b(0|1|2|3)\b/g,
			/\b(critical|high|medium|low|urgent|important|normal|optional)\b/gi
		];

		priorityPatterns.forEach((pattern) => {
			const matches = text.match(pattern);
			if (matches) {
				entities.priorities.push(...matches);
			}
		});

		// Extract modules (technical terms)
		const modulePatterns = [
			/\b(user|auth|login|payment|order|inventory|report|analytics|dashboard|api|database|backend|frontend|mobile|web)\b/gi,
			/\b(management|system|service|controller|model|view|component|module|feature|bug|improvement)\b/gi
		];

		modulePatterns.forEach((pattern) => {
			const matches = text.match(pattern);
			if (matches) {
				entities.modules.push(...matches);
			}
		});

		// Extract URLs
		const urlPattern = /\bhttps?:\/\/[^\s]+/g;
		const urls = text.match(urlPattern);
		if (urls) {
			entities.urls = urls;
		}

		// Extract emails
		const emailPattern = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g;
		const emails = text.match(emailPattern);
		if (emails) {
			entities.emails = emails;
		}

		return entities;
	}

	function mapEntitiesToFields(entities, currentField) {
		const mappings = {};

		// Map names to owner/created_by
		if (entities.names.length > 0) {
			if (currentField === 'owner' || !formData.owner) {
				mappings.owner = entities.names[0];
			}
			if (currentField === 'created_by' || !formData.created_by) {
				mappings.created_by = entities.names[0];
			}
		}

		// Map dates to due_date
		if (entities.dates.length > 0 && (currentField === 'due_date' || !formData.due_date)) {
			mappings.due_date = entities.dates[0];
		}

		// Map priorities
		if (entities.priorities.length > 0 && (currentField === 'priority' || !formData.priority)) {
			const priority = entities.priorities[0];
			// Convert to standard format
			const priorityMap = {
				'0': '0 - Critical',
				critical: '0 - Critical',
				urgent: '0 - Critical',
				'1': '1 - High',
				high: '1 - High',
				important: '1 - High',
				'2': '2 - Medium',
				medium: '2 - Medium',
				normal: '2 - Medium',
				'3': '3 - Low',
				low: '3 - Low',
				optional: '3 - Low'
			};
			mappings.priority = priorityMap[priority.toLowerCase()] || priority;
		}

		// Map modules
		if (entities.modules.length > 0 && (currentField === 'module' || !formData.module)) {
			mappings.module = entities.modules[0];
		}

		// Map URLs to reference_link
		if (
			entities.urls.length > 0 &&
			(currentField === 'reference_link' || !formData.reference_link)
		) {
			mappings.reference_link = entities.urls[0];
		}

		return mappings;
	}

	function updateUserSentiment(text) {
		const lowerText = text.toLowerCase();

		// Simple sentiment analysis
		if (
			lowerText.includes('frustrated') ||
			lowerText.includes('annoyed') ||
			lowerText.includes('angry')
		) {
			userSentiment = 'frustrated';
		} else if (
			lowerText.includes('confused') ||
			lowerText.includes('not sure') ||
			lowerText.includes('help')
		) {
			userSentiment = 'confused';
		} else if (
			lowerText.includes('thanks') ||
			lowerText.includes('thank you') ||
			lowerText.includes('great')
		) {
			userSentiment = 'happy';
		} else if (
			lowerText.includes('hurry') ||
			lowerText.includes('quick') ||
			lowerText.includes('asap')
		) {
			userSentiment = 'rushed';
		} else {
			userSentiment = 'neutral';
		}
	}

	// Enhanced attachment validation for Notion compatibility
	function validateAttachment(file) {
		const maxSize = 10 * 1024 * 1024; // 10MB
		if (file.size > maxSize) {
			return { valid: false, error: 'File ' + file.name + ' is too large. Maximum size is 10MB.' };
		}

		// Check for malicious file extensions
		const dangerousExtensions = ['.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js'];
		const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
		if (dangerousExtensions.includes(fileExtension)) {
			return {
				valid: false,
				error:
					'File ' +
					file.name +
					' has a potentially dangerous extension. Please upload a different file.'
			};
		}

		// Accept safe file types
		return { valid: true };
	}

	// Enhanced error handling with detailed logging
	function handleSubmissionError(error) {
		console.error('Submission error details:', {
			error: error,
			message: error?.message,
			stack: error?.stack,
			formData: formData,
			attachments: attachments.length,
			attempts: submissionAttempts
		});

		let errorMsg = '';
		let fieldToReprompt = null;
		let retryGuidance = '';

		// Enhanced error parsing - handle all possible error types
		if (typeof error === 'string') {
			errorMsg = error;
		} else if (error?.message) {
			errorMsg = error.message;
		} else if (error?.toString && typeof error.toString === 'function') {
			errorMsg = error.toString();
		} else if (error && typeof error === 'object') {
			// Try to extract meaningful information from object
			const errorKeys = Object.keys(error);
			if (errorKeys.length > 0) {
				errorMsg = 'Error: ' + errorKeys.join(', ');
			} else {
				errorMsg = 'An unknown error occurred during submission';
			}
		} else {
			errorMsg = 'An unknown error occurred during submission';
		}

		// Store last error for debugging
		lastError = {
			message: errorMsg,
			timestamp: new Date().toISOString(),
			formData: { ...formData },
			attachments: attachments.length
		};

		// Enhanced field identification
		const errorLower = errorMsg.toLowerCase();
		if (errorLower.includes('due_date') || errorLower.includes('date')) {
			fieldToReprompt = 'due_date';
			retryGuidance = 'Please provide a valid date in YYYY-MM-DD format.';
		} else if (errorLower.includes('owner')) {
			fieldToReprompt = 'owner';
			retryGuidance = 'Please provide a valid owner name.';
		} else if (errorLower.includes('type')) {
			fieldToReprompt = 'type';
			retryGuidance = 'Please select a valid type from the options.';
		} else if (errorLower.includes('priority')) {
			fieldToReprompt = 'priority';
			retryGuidance = 'Please select a valid priority level.';
		} else if (errorLower.includes('description')) {
			fieldToReprompt = 'description';
			retryGuidance =
				'Please provide a more detailed description (at least 15 characters with specific details).';
		} else if (errorLower.includes('title')) {
			fieldToReprompt = 'title';
			retryGuidance = 'Please provide a more descriptive title.';
		} else if (errorLower.includes('client')) {
			fieldToReprompt = 'client';
			retryGuidance = 'Please provide a valid client name.';
		} else if (errorLower.includes('module')) {
			fieldToReprompt = 'module';
			retryGuidance = 'Please specify which module this relates to.';
		}

		// Provide specific retry guidance
		if (fieldToReprompt) {
			return {
				message: 'Submission failed: ' + errorMsg + '. ' + retryGuidance,
				fieldToReprompt,
				retryGuidance
			};
		} else {
			// Generic retry guidance
			const guidance =
				submissionAttempts > 2
					? 'Please check your internet connection and try again. If the problem persists, contact support.'
					: 'Please review your answers and try again.';

			return {
				message: 'Submission failed: ' + errorMsg + '. ' + guidance,
				retryGuidance: guidance
			};
		}
	}

	// Enhanced submission with public URL generation
	async function submitToNotion() {
		submissionAttempts++;
		loading = true;
		state = 'submitting';

		chatFlow.push({ role: 'assistant', content: 'Submitting your request to Notion...' });
		chatFlow = [...chatFlow];
		await tick();
		scrollToBottom();

		try {
			// Only block if a required field is empty
			const requiredFields = [
				'title',
				'type',
				'description',
				'owner',
				'priority',
				'due_date',
				'created_by'
			];
			const missingRequired = requiredFields.filter(
				(f) => !formData[f] || formData[f].trim() === ''
			);
			if (missingRequired.length > 0) {
				throw new Error(
					'Missing required fields: ' + missingRequired.map((f) => fieldConfig[f].name).join(', ')
				);
			}
			// Validate summary quality
			const summaryIssues = validateSummary();
			if (summaryIssues.length > 0) {
				const warningMsg =
					'Please review before submitting:\n' +
					summaryIssues.map((issue) => '• ' + issue).join('\n');
				chatFlow.push({ role: 'assistant', content: warningMsg });
				chatFlow = [...chatFlow];
				await tick();
				scrollToBottom();
			}

			const submissionData = {
				title: formData.title,
				type: formData.type,
				client: formData.client,
				module: formData.module,
				description: formData.description,
				owner: formData.owner,
				priority: formData.priority,
				due_date: formData.due_date,
				reference_link: formData.reference_link,
				created_by: formData.created_by,
				attachments: attachments.map((f) => f.name),
				attachment_urls: attachmentUrls
			};

			// The createFeatureRequest function expects the data and optionally files
			// Since we already uploaded files separately, we pass null for files
			const result = await createFeatureRequest(localStorage.token, submissionData, null);

			let attachmentSummary = '';
			if (attachments.length > 0) {
				attachmentSummary += '\nFiles sent:\n' + attachments.map((f) => '- ' + f.name).join('\n');
			}
			if (attachmentUrls.length > 0) {
				attachmentSummary +=
					'\nAttachment URLs sent:\n' + attachmentUrls.map((u) => '- ' + u).join('\n');
			}

			// Create JSON data for download
			const jsonData = {
				...submissionData,
				submitted_at: new Date().toISOString(),
				submission_id: result?.id || 'req_' + Date.now(),
				status: 'submitted_to_notion'
			};

			// Create download link
			const jsonBlob = new Blob([JSON.stringify(jsonData, null, 2)], { type: 'application/json' });
			const downloadUrl = URL.createObjectURL(jsonBlob);
			const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
			const filename = 'db_request_' + timestamp + '.json';

			chatFlow.push({
				role: 'assistant',
				content:
					'✅ <b>Submission successful!</b> Your request was submitted to Notion.' +
					attachmentSummary +
					'<br><br>📄 <b>Download JSON:</b> <a href="' +
					downloadUrl +
					'" download="' +
					filename +
					'" style="color: #2563eb; text-decoration: underline;">Click here to download your request data</a> <span style="font-size: 0.95em; color: #666;">(filename: ' +
					filename +
					')</span><br><br>💡 You can save this JSON file for your records or use it for backup purposes.'
			});
			chatFlow = [...chatFlow];
			state = 'done';
			clearChatFlow();
		} catch (e) {
			console.error('Submission error:', e);
			let errorMessage =
				'There was a problem submitting your request. Please check your fields and try again.';
			let fieldToReprompt = null;

			if (typeof e === 'string') {
				errorMessage = e;
			} else if (e?.message) {
				// Try to parse Notion API error
				const notionMatch = /"message":"([^"]+)"/.exec(e.message);
				if (notionMatch) {
					errorMessage = notionMatch[1]
						.replace(/body failed validation. Fix one:/, 'Some fields are missing or invalid:')
						.replace(/should be defined, instead was 'undefined'\./g, '')
						.replace(/should be populated or 'null', instead was '""'\./g, '')
						.replace(/\n/g, '\n')
						.replace(/\s+/g, ' ')
						.trim();
					// Try to extract field
					if (/due date/i.test(errorMessage)) fieldToReprompt = 'due_date';
					if (/created by/i.test(errorMessage)) fieldToReprompt = 'created_by';
					if (/priority/i.test(errorMessage)) fieldToReprompt = 'priority';
					if (/owner/i.test(errorMessage)) fieldToReprompt = 'owner';
					if (/client/i.test(errorMessage)) fieldToReprompt = 'client';
					if (/module/i.test(errorMessage)) fieldToReprompt = 'module';
					if (/reference link/i.test(errorMessage)) fieldToReprompt = 'reference_link';
				} else {
					errorMessage = e.message;
				}
			} else if (e?.detail) {
				errorMessage = e.detail;
			}

			// Remove [object Object] from error messages
			errorMessage = errorMessage.replace(/\[object Object\]/g, 'Unknown error');

			if (fieldToReprompt) {
				chatFlow.push({ role: 'assistant', content: errorMessage });
				chatFlow = [...chatFlow];
				currentField = fieldToReprompt;
				state = 'editing';
				editingField = fieldToReprompt;
				const currentValue = formData[fieldToReprompt];
				chatFlow.push({
					role: 'assistant',
					content:
						'Please provide a new value for ' +
						fieldConfig[fieldToReprompt].name +
						'. Current value: "' +
						(currentValue || 'none') +
						'"'
				});
				chatFlow = [...chatFlow];
				isWaitingForInput = false;
				focusInput();
			} else {
				chatFlow.push({ role: 'assistant', content: errorMessage });
				chatFlow = [...chatFlow];
				state = 'review';
				isWaitingForInput = false;
				focusInput();
			}
			saveChatFlow();
		}

		loading = false;
		isSubmitting = false;
		scrollToBottom();
		isWaitingForInput = false;
	}

	// Enhanced reset functionality
	function resetForm() {
		// Clear all data
		clearChatFlow();
		chatFlow = [];
		attachments = [];
		attachmentUrls = [];
		attachmentUploadStatus = {};
		submissionAttempts = 0;
		lastError = null;

		// Reset form data
		formData = {
			title: '',
			type: '',
			client: '',
			module: '',
			description: '',
			owner: '',
			priority: '',
			due_date: '',
			reference_link: '',
			created_by: ''
		};

		// Reset field status
		fieldStatus = {
			title: 'pending',
			type: 'pending',
			client: 'pending',
			module: 'pending',
			description: 'pending',
			owner: 'pending',
			priority: 'pending',
			due_date: 'pending',
			reference_link: 'pending',
			created_by: 'pending'
		};

		// Reset state
		currentField = fieldOrder[0];
		state = 'asking';
		loading = false;
		isSubmitting = false;
		isWaitingForInput = false;
		editingField = null;
		lastSummary = '';
		userInput = '';

		// Start fresh
		askField(currentField);
		focusInput();
	}

	// Friendly acknowledgments per field
	const fieldAcknowledgments = {
		title: 'Oh, I got your title!',
		type: 'Thanks for specifying the type!',
		client: 'Thanks for providing the client!',
		module: 'Got your module!',
		description: 'Thanks for the detailed description!',
		owner: 'Owner noted!',
		priority: 'Priority set!',
		due_date: 'Due date received!',
		reference_link: 'Reference link recorded!',
		created_by: 'Thank you for letting me know who is creating this request!'
	};

	// Normalization helpers
	function normalizeField(field, value) {
		if (!value) return value;
		if (Array.isArray(value)) {
			return value.map((v) => normalizeField(field, v));
		}
		let v = value;
		if (typeof v !== 'string') return v;
		v = v.trim();
		if (field === 'title') {
			v = v.replace(/^the request is to\s*/i, '').replace(/^request is to\s*/i, '');
		}
		if (field === 'type') {
			if (/improvement/i.test(v)) return 'Improvement';
			if (/feature/i.test(v)) return 'Feature';
			if (/bug/i.test(v)) return 'Bug';
			if (/enhancement/i.test(v)) return 'Improvement';
			if (/1/i.test(v)) return 'High';
			if (/2/i.test(v)) return 'Medium';
			if (/3/i.test(v)) return 'Low';
			if (/0/i.test(v)) return 'Critical';
			return v.charAt(0).toUpperCase() + v.slice(1).toLowerCase();
		}
		if (field === 'client') {
			v = v
				.replace(/^(umm|probably|maybe|i think|i guess|perhaps|possibly|likely|probably)\s*/i, '')
				.replace(/^the client is\s*/i, '');
		}
		if (field === 'module') {
			v = v.replace(/^(i think it'?s|maybe|probably|the module is)\s*/i, '').replace(/,/g, ' ');
		}
		if (field === 'description') {
			v = v.charAt(0).toUpperCase() + v.slice(1);
		}
		if (field === 'owner' || field === 'created_by') {
			v = v
				.split(' ')
				.map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
				.join(' ');
		}
		if (field === 'priority') {
			if (v === '0' || /critical/i.test(v)) return '0 - Critical';
			if (v === '1' || /high/i.test(v)) return '1 - High';
			if (v === '2' || /medium/i.test(v)) return '2 - Medium';
			if (v === '3' || /low/i.test(v)) return '3 - Low';
		}
		if (field === 'due_date') {
			// Use dayjs to parse natural language dates
			const dayjsDate = dayjs(v, ['YYYY-MM-DD', 'DD/MM/YYYY'], true);
			if (dayjsDate.isValid()) return dayjsDate.format('YYYY-MM-DD');
			// Try natural language parsing
			const parsed = dayjs(v, { locale: 'en' });
			if (parsed.isValid()) return parsed.format('YYYY-MM-DD');
			// Try next monday, next week, etc.
			if (/next monday/i.test(v)) {
				const today = dayjs();
				const nextMonday = today.day() <= 1 ? today.day(1) : today.add(1, 'week').day(1);
				return nextMonday.format('YYYY-MM-DD');
			}
			return v;
		}
		if (field === 'reference_link' || field === 'attachments') {
			if (/^(none|no|n\/a|n-a|n a|skip|remove|delete|clear)$/i.test(v)) return '';
		}
		return v;
	}

	async function handleFieldInput(input) {
		const field = currentField;

		// Use enhanced processFieldInput for name suggestion fields
		if (NAME_SUGGESTION_FIELDS.includes(field)) {
			await processFieldInput(field, input);
			return;
		}

		chatFlow.push({ role: 'user', content: input });
		chatFlow = [...chatFlow];
		await tick();
		scrollToBottom();

		// Validate the input
		const validation = validateField(field, input);
		if (typeof validation === 'string') {
			// Show error and re-prompt for the same field
			chatFlow.push({ role: 'assistant', content: validation });
			chatFlow = [...chatFlow];
			saveChatFlow();
			await tick();
			scrollToBottom();
			focusInput();
			return;
		}

		// Valid input
		let value = validation.correctedValue;
		value = normalizeField(field, value);
		if (MULTI_FIELDS.includes(field)) {
			formData[field] = value;
		} else {
			formData[field] = value;
		}
		formData = { ...formData };
		fieldStatus[field] = 'completed';
		fieldStatus = { ...fieldStatus };
		completionPercentage = calculateProgress();

		if (state === 'editing') {
			editingField = null;
			state = 'review';
			await showSummary();
			focusInput();
			return;
		}

		const nextIdx = fieldOrder.indexOf(currentField) + 1;
		if (nextIdx < fieldOrder.length) {
			const nextField = fieldOrder[nextIdx];
			currentField = nextField;
			state = 'asking';
			const ack = fieldAcknowledgments[field] || 'Got it!';
			let nextPrompt = '';
			if (nextField === 'title')
				nextPrompt =
					'What is the title of your DB request? Please provide a clear, descriptive name.';
			else if (nextField === 'type')
				nextPrompt =
					'What type of request is this? Options: ' + fieldConfig[nextField].options.join(', ');
			else if (nextField === 'client')
				nextPrompt = 'Who is the client or business unit requesting this?';
			else if (nextField === 'module')
				nextPrompt = 'Which module or specific part of the system does this relate to?';
			else if (nextField === 'description')
				nextPrompt =
					'Please describe the requirement in detail. Include specific details about what needs to be implemented or fixed. Minimum 15 characters.';
			else if (nextField === 'owner')
				nextPrompt = 'Who will be the owner responsible for this request?';
			else if (nextField === 'priority')
				nextPrompt =
					'What is the priority level? Enter 0 for Critical, 1 for High, 2 for Medium, or 3 for Low. You can also type the word (e.g., "critical").';
			else if (nextField === 'due_date')
				nextPrompt =
					'What is the expected completion or delivery date? (e.g., 2025-07-20 or "next week")';
			else if (nextField === 'reference_link')
				nextPrompt =
					'Do you have any reference links or URLs related to this request? (If not applicable, type "skip", "n/a", or "none")';
			else if (nextField === 'created_by')
				nextPrompt = 'Who is creating this request? (Full name required)';
			chatFlow.push({ role: 'assistant', content: ack + ' ' + nextPrompt });
			chatFlow = [...chatFlow];
			saveChatFlow();
			await tick();
			scrollToBottom();
			focusInput();
			return;
		}

		await showSummary();
		focusInput();
	}

	// Enhanced summary validation
	function validateSummary() {
		const issues = [];

		// Check for vague descriptions
		if (formData.description) {
			const vagueWords = ['same', 'usual', 'fix', 'improve', 'enhance', 'update'];
			const hasVagueContent = vagueWords.some((word) =>
				formData.description.toLowerCase().includes(word)
			);

			if (hasVagueContent && formData.description.length < 30) {
				issues.push('Description could be more specific');
			}
		}

		// Check for short titles
		if (formData.title && formData.title.length < 5) {
			issues.push('Title is quite short');
		}

		// Check for missing critical fields
		const criticalFields = ['title', 'type', 'description', 'owner', 'priority'];
		const missingCritical = criticalFields.filter(
			(field) => !formData[field] || formData[field].trim() === ''
		);

		if (missingCritical.length > 0) {
			issues.push(
				'Missing critical fields: ' + missingCritical.map((f) => fieldConfig[f].name).join(', ')
			);
		}

		return issues;
	}

	// Enhanced URL validation
	function validateUrl(url) {
		try {
			new URL(url);
			return { valid: true };
		} catch {
			return {
				valid: false,
				error: 'Please provide a valid URL starting with http:// or https://'
			};
		}
	}

	function getPendingFields() {
		return REQUIRED_FIELDS.filter((f) => {
			// Check if field is empty
			return !formData[f] || formData[f].trim() === '';
		});
	}

	async function handleUserSubmit() {
		if (
			!userInput.trim() ||
			isProcessing ||
			state === 'submitting' ||
			state === 'done' ||
			loading ||
			isSubmitting
		)
			return;

		const input = userInput.trim();
		userInput = '';
		isWaitingForInput = true;

		// Fallback commands
		if (input.toLowerCase() === 'retry') {
			await submitToNotion();
			return;
		}
		if (input.toLowerCase() === 'save') {
			localStorage.setItem(
				'artifactFormFallback',
				JSON.stringify({
					formData,
					attachments: attachments.map((f) => ({ name: f.name, size: f.size, type: f.type })),
					attachmentUrls
				})
			);
			chatFlow.push({
				role: 'assistant',
				content: 'Your request has been saved locally. You can retry later.'
			});
			chatFlow = [...chatFlow];
			isWaitingForInput = false;
			return;
		}
		if (input.toLowerCase() === 'export') {
			const data = JSON.stringify(
				{
					formData,
					attachments: attachments.map((f) => ({ name: f.name, size: f.size, type: f.type })),
					attachmentUrls
				},
				null,
				2
			);
			const blob = new Blob([data], { type: 'application/json' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = 'project-request.json';
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
			chatFlow.push({ role: 'assistant', content: 'Your request has been exported as JSON.' });
			chatFlow = [...chatFlow];
			isWaitingForInput = false;
			return;
		}

		// Handle special commands FIRST - these should work in any state
		if (input.toLowerCase() === 'submit') {
			await handleSubmit();
			return;
		}

		if (input.toLowerCase() === 'submit anyway') {
			await submitToNotion();
			return;
		}

		if (input.toLowerCase() === 'help') {
			chatFlow.push({
				role: 'assistant',
				content:
					"🤝 I'm here to help you fill out your DB request! Here's what you can do:\n\n" +
					'🔄 Commands:\n' +
					'• "help" - Show this help message\n' +
					'• "submit" - Send your request to Notion\n' +
					'• "edit [field]" - Edit a specific field (e.g., "edit title")\n' +
					'• "debug" - Show current form data\n' +
					'• "cancel" - Cancel the request\n\n' +
					'💡 Field Tips:\n' +
					'• Required fields (Title, Type, Description, Owner, Priority, Due Date) must be filled\n' +
					'• Optional fields (Client, Module, Reference Link) can be "skip" or "n/a"\n' +
					'• Attachments are optional - you can add files using the controls on the right\n\n' +
					'What would you like to tell me about your request?'
			});
			chatFlow = [...chatFlow];

			// Continue to next field after showing help
			if (state === 'asking') {
				await askField(currentField);
			}
			isWaitingForInput = false;
			return;
		}

		if (input.toLowerCase() === 'debug') {
			const debugInfo =
				'Current Form Data:\n' +
				JSON.stringify(formData, null, 2) +
				'\n\nField Status:\n' +
				JSON.stringify(fieldStatus, null, 2);
			chatFlow.push({ role: 'assistant', content: debugInfo });
			chatFlow = [...chatFlow];

			// Continue to next field after showing debug info
			if (state === 'asking') {
				await askField(currentField);
			}
			isWaitingForInput = false;
			return;
		}

		if (input.toLowerCase().startsWith('edit ')) {
			await handleEdit(input.substring(5));
			return;
		}

		if (input.toLowerCase() === 'cancel') {
			await handleCancel();
			return;
		}

		// Only handle field input if we're in asking or editing state
		if (state === 'asking' || state === 'editing') {
			// Check if suggestions are currently showing
			if (showingSuggestions && suggestionField === currentField) {
				await handleSuggestionSelection(input);
				return;
			}

			// Check if this is a name field and show suggestions
			if (NAME_SUGGESTION_FIELDS.includes(currentField) && input.length >= 2) {
				// Add user input to chat first
				chatFlow.push({ role: 'user', content: input });
				chatFlow = [...chatFlow];
				await tick();
				scrollToBottom();

				// Then show suggestions
				userInput = input; // Restore the input for suggestion handling
				await handleNameSuggestionInput();
				return;
			}

			await handleUserInputWithAI(input);
		} else if (state === 'review') {
			// Handle review state responses
			chatFlow.push({ role: 'user', content: input });

			if (input.toLowerCase().includes('no attachment') || input.toLowerCase() === 'no') {
				// User doesn't want to add attachments, proceed to final review
				chatFlow.push({
					role: 'assistant',
					content: "Got it! No attachments needed. Let's review your request:"
				});
				chatFlow = [...chatFlow];
				await tick();
				scrollToBottom();

				const summary = Object.entries(formData)
					.map(([k, v]) => fieldConfig[k].name + ': ' + v)
					.join('\n');
				const finalReviewMsg =
					'Review your request before submitting:\n\n' +
					summary +
					'\n\nType Submit to send, Edit [field] to change an answer, or Cancel to abort.';

				chatFlow.push({ role: 'assistant', content: finalReviewMsg });
				chatFlow = [...chatFlow];
				lastSummary = finalReviewMsg;
				await tick();
				scrollToBottom();
			} else if (input.toLowerCase() === 'submit') {
				await handleSubmit();
			} else if (input.toLowerCase().startsWith('edit ')) {
				await handleEdit(input.substring(5));
			} else if (input.toLowerCase() === 'cancel') {
				await handleCancel();
			} else if (input.toLowerCase() === 'done') {
				await showSummary();
			} else {
				// User might be trying to add attachments via text
				chatFlow.push({
					role: 'assistant',
					content:
						'You can add attachments using the file upload controls on the right side, or type "no attachments" to proceed without files.'
				});
				chatFlow = [...chatFlow];
			}

			await tick();
			scrollToBottom();
			isWaitingForInput = false;
			focusInput();
		}
	}

	async function handleEdit(fieldName) {
		// Find the field by name (case insensitive)
		const fieldKey = fieldOrder.find(
			(f) =>
				fieldConfig[f].name.toLowerCase() === fieldName.toLowerCase() ||
				f.toLowerCase() === fieldName.toLowerCase()
		);

		if (!fieldKey) {
			chatFlow.push({
				role: 'assistant',
				content:
					'❌ Unknown field "' +
					fieldName +
					'". Available fields: ' +
					fieldOrder.map((f) => fieldConfig[f].name).join(', ')
			});
			chatFlow = [...chatFlow];
			await tick();
			scrollToBottom();
			isWaitingForInput = false;
			focusInput();
			return;
		}

		editingField = fieldKey;
		currentField = fieldKey;
		state = 'editing';

		// Re-validate the field being edited
		const currentValue = formData[fieldKey];
		if (currentValue) {
			const validation = validateField(fieldKey, currentValue);
			if (typeof validation === 'string') {
				// Current value is invalid, show warning
				chatFlow.push({
					role: 'assistant',
					content:
						'⚠️ Current value for ' +
						fieldConfig[fieldKey].name +
						' may need improvement: ' +
						validation
				});
				chatFlow = [...chatFlow];
			}
		}

		// Don't ask the field again - just prompt for new value
		chatFlow.push({
			role: 'assistant',
			content:
				'Please provide a new value for ' +
				fieldConfig[fieldKey].name +
				'. Current value: "' +
				(currentValue || 'none') +
				'"'
		});
		chatFlow = [...chatFlow];
		await tick();
		scrollToBottom();
		isWaitingForInput = false;
		focusInput();
	}

	async function handleSubmit() {
		// Only check required fields, not all fields
		const requiredFields = [
			'title',
			'type',
			'description',
			'owner',
			'priority',
			'due_date',
			'created_by'
		];
		const missing = requiredFields.filter(
			(f) =>
				!formData[f] ||
				(Array.isArray(formData[f]) ? formData[f].length === 0 : formData[f].trim() === '')
		);

		const needReview = Object.entries(formData)
			.filter(([k, v]) => v === 'TBD' && (k === 'client' || k === 'module'))
			.map(([k]) => fieldConfig[k].name);

		// If no missing required fields, submit directly
		if (missing.length === 0) {
			await submitToNotion();
			return;
		}

		// Do not allow submit anyway if created_by is missing
		if (missing.includes('created_by')) {
			let msg = 'Review before submitting:';
			msg +=
				'\nMissing: ' +
				missing.map((f) => fieldConfig[f].name).join(', ') +
				'\n\nPlease provide your full name for Created By. This field is required.';
			chatFlow.push({ role: 'assistant', content: msg });
			chatFlow = [...chatFlow];
			saveChatFlow();
			scrollToBottom();
			isWaitingForInput = false;
			focusInput();
			return;
		}

		let msg = 'Review before submitting:';
		if (missing.length > 0) {
			msg += '\nMissing: ' + missing.map((f) => fieldConfig[f].name).join(', ') + '\n';
		}
		if (needReview.length > 0) {
			msg += '\nNeed Review: ' + needReview.join(', ') + '\n';
		}
		msg +=
			'\n\nType "submit anyway" to submit with these fields as TBD, or fill them in and type submit again.';
		chatFlow.push({ role: 'assistant', content: msg });
		chatFlow = [...chatFlow];
		saveChatFlow();
		scrollToBottom();
		return;
	}

	async function handleCancel() {
		chatFlow.push({
			role: 'assistant',
			content: 'Request cancelled. You can start over or close this form.'
		});
		chatFlow = [...chatFlow];
		state = 'done';
		await tick();
		scrollToBottom();
		isWaitingForInput = false;
		focusInput();
	}

	async function askField(field) {
		const fieldInfo = fieldConfig[field];
		let prompt = '';

		if (field === 'title') {
			prompt = 'What is the title of your DB request? Please provide a clear, descriptive name.';
		} else if (field === 'type') {
			prompt = 'What type of request is this? Options: ' + fieldInfo.options.join(', ');
		} else if (field === 'client') {
			prompt = 'Who is the client or business unit requesting this?';
		} else if (field === 'module') {
			prompt = 'Which module or specific part of the system does this relate to?';
		} else if (field === 'description') {
			prompt =
				'Please describe the requirement in detail. Include specific details about what needs to be implemented or fixed. Minimum 15 characters.';
		} else if (field === 'owner') {
			prompt =
				'Who will be the owner responsible for this request? (Type a name to see matching suggestions)';
		} else if (field === 'priority') {
			prompt =
				'What is the priority level? Enter 0 for Critical, 1 for High, 2 for Medium, or 3 for Low. You can also type the word (e.g., "critical").';
		} else if (field === 'due_date') {
			prompt =
				'What is the expected completion or delivery date? (e.g., 2025-07-20 or "next week")';
		} else if (field === 'reference_link') {
			prompt =
				'Do you have any reference links or URLs related to this request? (If not applicable, type "skip", "n/a", or "none")';
		} else if (field === 'created_by') {
			prompt = 'Who is creating this request? (Type a name to see matching suggestions)';
		}

		chatFlow.push({ role: 'assistant', content: prompt });
		chatFlow = [...chatFlow];
		await tick();
		scrollToBottom();
		isWaitingForInput = false;
		focusInput();
	}

	async function showSummary() {
		// Use the new checkFieldsForChanges function
		const fieldAnalysis = checkFieldsForChanges();

		if (!fieldAnalysis.hasIssues) {
			// No changes required - show success message and continue
			let summary = '## 📋 Form Review\n';
			ALL_FIELDS.forEach((field) => {
				const fieldInfo = fieldConfig[field];
				const value = formData[field] || 'Not provided';
				const status = fieldStatus[field];
				const statusIcon = status === 'completed' ? '✅' : status === 'skipped' ? '🟡' : '❌';

				if (fieldInfo) {
					summary += statusIcon + ' ' + fieldInfo.name + ': ' + value + '\n';
				} else {
					summary += statusIcon + ' ' + field + ': ' + value + '\n';
				}
			});

			summary += '\n📊 Progress: ' + completionPercentage + '% complete';
			summary += '\n\nType "submit" to submit your request.';

			chatFlow.push({ role: 'assistant', content: summary });
			chatFlow = [...chatFlow];
			scrollToBottom();
			return;
		}

		// Fields need changes - show what needs to be fixed
		let summary = '## 📋 Form Review - Changes Required\n\n';

		// Show critical issues first
		if (fieldAnalysis.fieldsNeedingChanges.length > 0) {
			summary += '🔴 Critical Issues (' + fieldAnalysis.fieldsNeedingChanges.length + '):\n';
			fieldAnalysis.fieldsNeedingChanges.forEach((item) => {
				summary += '• ' + item.name + ': ' + item.issue + '\n';
			});
			summary += '\n';
		}

		// Show warnings/suggestions
		if (fieldAnalysis.fieldsNeedingReview.length > 0) {
			summary += '🟡 Suggestions (' + fieldAnalysis.fieldsNeedingReview.length + '):\n';
			fieldAnalysis.fieldsNeedingReview.forEach((item) => {
				summary += '• ' + item.name + ': ' + item.issue + '\n';
			});
			summary += '\n';
		}

		// Show all fields with their current values and status
		summary += '📝 Current Form Status:\n';
		ALL_FIELDS.forEach((field) => {
			const fieldInfo = fieldConfig[field];
			const value = formData[field] || 'Not provided';
			const status = fieldStatus[field];
			const statusIcon = status === 'completed' ? '✅' : status === 'skipped' ? '🟡' : '❌';

			// Check if this field has issues
			const hasCriticalIssue = fieldAnalysis.fieldsNeedingChanges.some(
				(item) => item.field === field
			);
			const hasWarning = fieldAnalysis.fieldsNeedingReview.some((item) => item.field === field);

			let fieldIcon = statusIcon;
			if (hasCriticalIssue) fieldIcon = '🔴';
			else if (hasWarning) fieldIcon = '🟡';

			if (fieldInfo) {
				summary += fieldIcon + ' ' + fieldInfo.name + ': ' + value + '\n';
			} else {
				summary += fieldIcon + ' *' + field + ': ' + value + '\n';
			}
		});

		summary += '\n📊 Progress: ' + completionPercentage + '% complete\n\n';
		summary += '💡 To fix issues:\n';
		summary += '• Type "edit [field name]" to edit a specific field\n';
		summary += '• Type "help" for guidance on any field\n';
		summary += '• Type "submit anyway" to proceed with current data\n';

		chatFlow.push({ role: 'assistant', content: summary });
		chatFlow = [...chatFlow];
		scrollToBottom();
	}

	onMount(async () => {
		// Initialize new form (no session persistence)
		clearChatFlow();
		chatFlow = [];
		currentField = fieldOrder[0];
		formData = {
			title: '',
			type: '',
			client: '',
			module: '',
			description: '',
			owner: '',
			priority: '',
			due_date: '',
			reference_link: '',
			created_by: ''
		};
		fieldStatus = {
			title: 'pending',
			type: 'pending',
			client: 'pending',
			module: 'pending',
			description: 'pending',
			owner: 'pending',
			priority: 'pending',
			due_date: 'pending',
			reference_link: 'pending',
			created_by: 'pending'
		};
		attachments = [];
		attachmentUrls = [];
		userInput = '';
		state = 'asking';
		loading = false;
		errorMsg = '';
		editingField = null;
		lastSummary = '';
		isWaitingForInput = false;

		// Initialize with AI greeting
		await initializeWithAI();

		// Focus input
		focusInput();
	});

	// AI-powered chatbot functionality
	let aiContext = {
		currentField: null,
		conversationHistory: [],
		userIntent: null,
		extractedInfo: {},
		confidence: 0
	};

	// Optimized OpenAI integration with caching and fallback
	let aiCache = new Map();
	let lastAICall = 0;
	const AI_CALL_COOLDOWN = 1000; // 1 second cooldown between calls

	async function callOpenAI(messages) {
		try {
			// Check if we have a valid token
			const token = localStorage.token;
			if (!token) {
				console.warn('No authentication token found, using fallback');
				return null;
			}

			// Rate limiting to prevent too many calls
			const now = Date.now();
			if (now - lastAICall < AI_CALL_COOLDOWN) {
				// console.log('AI call rate limited, using fallback');
				return null;
			}
			lastAICall = now;

			// Simple caching for repeated requests
			const cacheKey = JSON.stringify(messages);
			if (aiCache.has(cacheKey)) {
				// console.log('Using cached AI response');
				return aiCache.get(cacheKey);
			}

			const response = await fetch('/api/chat/completions', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: 'Bearer ' + token
				},
				body: JSON.stringify({
					model: 'gpt-4o-mini',
					messages: messages,
					temperature: 0.7,
					max_tokens: 500, // Reduced for faster responses
					stream: false
				})
			});

			if (!response.ok) {
				const errorText = await response.text();
				console.error('OpenAI API error:', response.status, errorText);

				// If it's an authentication error, try to redirect to login
				if (response.status === 401 || response.status === 403) {
					console.warn('Authentication required, redirecting to login');
					window.location.href = '/auth';
					return null;
				}

				throw new Error('OpenAI API call failed: ' + response.status + ' ' + errorText);
			}

			const data = await response.json();
			const result = data.choices[0].message.content;

			// Cache the result
			aiCache.set(cacheKey, result);

			// Limit cache size
			if (aiCache.size > 50) {
				const firstKey = aiCache.keys().next().value;
				aiCache.delete(firstKey);
			}

			return result;
		} catch (error) {
			console.error('OpenAI API error:', error);
			return null;
		}
	}

	// Enhanced AI-powered field extraction and validation with comprehensive rules
	async function processUserResponseWithAI(userInput) {
		const systemPrompt =
			'You are a FAST, INTELLIGENT, and HELPFUL DB request form assistant with advanced AI capabilities. You process EVERY field with AI validation and handle natural conversation flow.\n\n' +
			'CRITICAL RULES:\n' +
			'1. EVERY FIELD MUST BE PROCESSED BY AI - no exceptions\n' +
			'2. REJECT vague inputs like "how to fill this", "now what", "help", "i dont know"\n' +
			'3. PROVIDE helpful guidance for vague inputs instead of processing as data\n' +
			'4. VALIDATE every input thoroughly before accepting\n' +
			'5. MAINTAIN natural conversation flow\n' +
			'6. DETECT user intent and sentiment\n' +
			'7. FIX typos and normalize data automatically\n' +
			'8. EXTRACT multiple fields from single responses when possible\n\n' +
			'FORM FIELDS & REQUIREMENTS:\n' +
			'1. title: Descriptive title (3+ chars, professional, no vague terms)\n' +
			'2. type: "Feature", "Bug", or "Improvement" (case-insensitive)\n' +
			'3. description: Detailed explanation (15+ chars, meaningful content)\n' +
			'4. priority: "0 - Critical", "1 - High", "2 - Medium", "3 - Low"\n' +
			'5. owner: Full name of responsible person (no partial names like "din1")\n' +
			'6. created_by: Full name of person creating request (no partial names)\n' +
			'7. client: Team/department/client name\n' +
			'8. module: Specific system module or feature\n' +
			'9. due_date: Valid future date or natural language\n' +
			'10. reference_link: Valid URL or empty\n\n' +
			'CURRENT STATE:\n' +
			'- Current field: ' +
			(currentField || 'title') +
			'\n' +
			'- Form data: ' +
			JSON.stringify(formData) +
			'\n' +
			'- User input: "' +
			userInput +
			'"\n\n' +
			'VAGUE INPUT DETECTION:\n' +
			'REJECT these inputs and provide guidance instead:\n' +
			'- "how to fill this", "now what", "what should i do"\n' +
			'- "i dont know", "not sure", "maybe", "um"\n' +
			'- "ok", "same", "test", "hello"\n' +
			'- Questions ending with "?"\n' +
			'- Very short inputs (< 3 chars) unless they are valid options\n' +
			"- Generic responses that don't provide actual data\n\n" +
			'AI PROCESSING RULES:\n' +
			'1. VAGUE INPUT HANDLING: If input is vague, set isVague=true and provide guidance\n' +
			'2. FIELD VALIDATION: Validate every field with specific rules\n' +
			'3. TYPO CORRECTION: Fix common typos automatically\n' +
			'4. MULTI-FIELD EXTRACTION: Extract multiple fields when possible\n' +
			'5. SENTIMENT ANALYSIS: Detect user mood and adapt response tone\n' +
			'6. CONTEXT AWARENESS: Remember previous answers and maintain flow\n' +
			'7. NATURAL LANGUAGE: Understand conversational inputs\n' +
			'8. PROGRESS TRACKING: Always move to next field after valid input\n\n' +
			'VALIDATION RULES:\n' +
			'- title: Must be descriptive, 3+ chars, no vague terms\n' +
			'- type: Must be Feature/Bug/Improvement\n' +
			'- description: Must be detailed, 15+ chars, meaningful\n' +
			'- priority: Must be valid priority level\n' +
			'- owner/created_by: Must be full names, no partial names\n' +
			'- due_date: Must be valid future date\n' +
			'- reference_link: Must be valid URL or empty\n\n' +
			'RESPONSE FORMAT (JSON):\n' +
			'{\n' +
			'  "isVague": true/false,\n' +
			'  "vagueReason": "explanation if vague",\n' +
			'  "guidance": "helpful guidance if vague",\n' +
			'  "extracted_data": {\n' +
			'    "field_name": "extracted_value"\n' +
			'  },\n' +
			'  "validation": {\n' +
			'    "valid": true/false,\n' +
			'    "message": "validation message if invalid",\n' +
			'    "suggestions": ["suggested corrections"]\n' +
			'  },\n' +
			'  "sentiment": "frustrated/confused/happy/rushed/neutral",\n' +
			'  "user_intent": "provide_info/edit_previous/ask_help/skip/complete",\n' +
			'  "next_action": "continue/ask_clarification/help/edit_previous/skip/summary",\n' +
			'  "response": "friendly, concise response adapted to sentiment",\n' +
			'  "confidence": 0.0-1.0,\n' +
			'  "tone": "empathetic/encouraging/concise/patient"\n' +
			'}';

		const messages = [
			{ role: 'system', content: systemPrompt },
			{ role: 'user', content: userInput }
		];

		const aiResponse = await callOpenAI(messages);

		if (!aiResponse) {
			// Fallback to rule-based validation
			return processUserResponseFallback(userInput);
		}

		try {
			const parsed = JSON.parse(aiResponse);

			// Handle vague inputs detected by AI
			if (parsed.isVague) {
				return {
					...parsed,
					extracted_data: {}, // No data extracted for vague inputs
					validation: { valid: false, message: parsed.vagueReason },
					response: parsed.guidance || parsed.vagueReason
				};
			}

			return parsed;
		} catch (error) {
			console.error('Failed to parse AI response:', error);
			return processUserResponseFallback(userInput);
		}
	}

	// Enhanced fallback rule-based processing
	function processUserResponseFallback(userInput) {
		const sanitizedInput = sanitizeInput(userInput.trim());

		// First, try to extract multiple fields from the input
		const extractedFields = extractMultipleFields(userInput);
		// console.log('Extracted fields from fallback:', extractedFields);

		if (Object.keys(extractedFields).length > 0) {
			// We found multiple fields, process them
			let responseMessage = "I've extracted the following information:\n";
			let processedFields = 0;
			let hasValidationErrors = false;

			for (const [fieldName, fieldValue] of Object.entries(extractedFields)) {
				if (fieldValue && fieldValue.trim()) {
					const validation = validateField(fieldName, fieldValue);
					if (typeof validation === 'string') {
						// Validation failed
						hasValidationErrors = true;
						responseMessage +=
							'\n⚠️ ' + (fieldConfig[fieldName]?.name || fieldName) + ': ' + validation;
					} else if (validation.valid) {
						// Validation passed
						formData[fieldName] = validation.correctedValue;
						processedFields++;
						responseMessage +=
							'\n✅ ' +
							(fieldConfig[fieldName]?.name || fieldName) +
							': ' +
							validation.correctedValue;
					}
				}
			}

			if (processedFields > 0 && !hasValidationErrors) {
				updateFieldStatus();
				editingField = null;

				const nextField = getNextField();
				if (nextField) {
					const fieldInfo = fieldConfig[nextField];
					responseMessage += '\n\n' + (fieldInfo?.description || 'Please provide ' + nextField);
					currentField = nextField;
				} else {
					responseMessage +=
						'\n\n🎉 All required fields complete! Would you like to review your request or submit it?';
				}
			}

			return {
				extracted_data: extractedFields,
				validation: { valid: !hasValidationErrors },
				response: responseMessage,
				confidence: 0.8
			};
		}

		// Use current field if available, otherwise detect
		let detectedField = currentField || getNextField();

		// Quick validation for common patterns
		if (detectedField === 'priority') {
			// Handle priority numbers and text
			const priorityMap = {
				'0': '0 - Critical',
				critical: '0 - Critical',
				urgent: '0 - Critical',
				'1': '1 - High',
				high: '1 - High',
				important: '1 - High',
				'2': '2 - Medium',
				medium: '2 - Medium',
				normal: '2 - Medium',
				'3': '3 - Low',
				low: '3 - Low',
				optional: '3 - Low'
			};

			const normalized = sanitizedInput.toLowerCase();
			if (priorityMap[normalized]) {
				return {
					extracted_data: { priority: priorityMap[normalized] },
					validation: { valid: true },
					response: 'I\'ve recorded "' + priorityMap[normalized] + '" for Priority.',
					confidence: 0.9
				};
			}
		}

		if (detectedField === 'type') {
			// Handle type with typo correction
			const typeMap = {
				feature: 'Feature',
				featrue: 'Feature',
				featue: 'Feature',
				bug: 'Bug',
				bog: 'Bug',
				improvement: 'Improvement',
				improvment: 'Improvement'
			};

			const normalized = sanitizedInput.toLowerCase();
			if (typeMap[normalized]) {
				return {
					extracted_data: { type: typeMap[normalized] },
					validation: { valid: true },
					response: 'I\'ve recorded "' + typeMap[normalized] + '" for Type.',
					confidence: 0.9
				};
			}
		}

		// Default processing
		const validation = validateField(detectedField, sanitizedInput);

		if (typeof validation === 'string') {
			// Validation failed
			return {
				extracted_data: { [detectedField]: sanitizedInput },
				validation: { valid: false, message: validation },
				response: '⚠️ ' + (fieldConfig[detectedField]?.name || detectedField) + ': ' + validation,
				confidence: 0.3
			};
		} else if (validation.valid) {
			// Validation passed
			return {
				extracted_data: { [detectedField]: validation.correctedValue },
				validation: { valid: true },
				response:
					'I\'ve recorded "' +
					validation.correctedValue +
					'" for ' +
					(fieldConfig[detectedField]?.name || detectedField) +
					'.',
				confidence: 0.8
			};
		}

		// Fallback for unclear input
		return {
			extracted_data: { [detectedField]: sanitizedInput },
			validation: { valid: false, message: 'Please provide more specific details.' },
			response:
				"I understand you're providing information for " +
				(fieldConfig[detectedField]?.name || detectedField) +
				'. Please provide more specific details.',
			confidence: 0.4
		};
	}

	// Enhanced user input processing with AI
	async function handleUserInputWithAI(userInput) {
		// Add user message to chat
		chatFlow.push({ role: 'user', content: userInput });

		// Handle special commands first (instant responses for better performance)
		const lowerInput = userInput.toLowerCase().trim();

		// Update user sentiment based on input
		updateUserSentiment(userInput);

		// ALWAYS process input with AI first - no exceptions
		const aiResult = await processUserResponseWithAI(userInput);

		// Handle vague inputs detected by AI
		if (aiResult && aiResult.isVague) {
			chatFlow.push({ role: 'assistant', content: aiResult.guidance || aiResult.response });
			chatFlow = [...chatFlow];
			await tick();
			scrollToBottom();
			return;
		}

		// Handle special commands first (these bypass AI processing)
		if (lowerInput === 'help' || lowerInput.includes('help')) {
			await showFieldHelp();
			return;
		}
		if (
			lowerInput === 'summary' ||
			lowerInput.includes('summary') ||
			lowerInput === 'review' ||
			lowerInput.includes('review')
		) {
			await showSummary();
			return;
		}
		if (lowerInput === 'back' || lowerInput.includes('back')) {
			await goToPreviousField();
			return;
		}
		if (lowerInput === 'clear' || lowerInput.includes('clear')) {
			await clearCurrentField();
			return;
		}
		if (lowerInput === 'restart' || lowerInput.includes('restart')) {
			window.location.reload();
			return;
		}
		if (lowerInput === 'cancel' || lowerInput.includes('cancel')) {
			chatFlow.push({
				role: 'assistant',
				content: "I've cancelled the current operation. What would you like to do next?"
			});
			chatFlow = [...chatFlow];
			saveChatFlow();
			scrollToBottom();
			return;
		}
		if (lowerInput === 'skip' || lowerInput.includes('skip')) {
			await handleSkipField();
			return;
		}

		// Handle edit command
		const editMatch = userInput.toLowerCase().match(/edit\s+(\w+)/);
		if (editMatch) {
			const fieldToEdit = editMatch[1];
			const matchedField = ALL_FIELDS.find(
				(f) =>
					f.toLowerCase().includes(fieldToEdit) ||
					fieldConfig[f]?.name.toLowerCase().includes(fieldToEdit)
			);
			if (matchedField) {
				editingField = matchedField;
				chatFlow.push({
					role: 'assistant',
					content: `I'm ready to edit the ${fieldConfig[matchedField]?.name || matchedField} field. Current value: "${formData[matchedField] || 'empty'}". What would you like to change it to?`
				});
				chatFlow = [...chatFlow];
				saveChatFlow();
				scrollToBottom();
				return;
			} else {
				chatFlow.push({
					role: 'assistant',
					content: `I couldn't find a field called "${fieldToEdit}". Available fields: ${ALL_FIELDS.map((f) => fieldConfig[f]?.name || f).join(', ')}`
				});
				chatFlow = [...chatFlow];
				saveChatFlow();
				scrollToBottom();
				return;
			}
		}

		// Handle name suggestion selection
		if (showingSuggestions && suggestionField === currentField) {
			const num = parseInt(userInput);
			if (num >= 1 && num <= nameSuggestions.length) {
				const selectedSuggestion = nameSuggestions[num - 1];
				await processFieldInput(currentField, selectedSuggestion.name);
				return;
			}
		}

		// Process the AI result
		if (aiResult && aiResult.extracted_data && Object.keys(aiResult.extracted_data).length > 0) {
			// Process extracted data
			if (!editingField && state === 'asking') {
				// Normal field-by-field flow - only process current field
				const currentFieldValue = aiResult.extracted_data[currentField];
				if (currentFieldValue && currentFieldValue.trim()) {
					let valueToValidate = currentFieldValue;

					// Special handling for due_date
					if (currentField === 'due_date') {
						const parsedDate = parseDate(currentFieldValue);
						if (parsedDate) {
							valueToValidate = parsedDate;
						}
					}

					const validation = validateField(currentField, valueToValidate);
					if (typeof validation === 'string') {
						chatFlow.push({ role: 'assistant', content: validation });
					} else if (validation.valid) {
						formData[currentField] = validation.correctedValue;
						formData = { ...formData };
						fieldStatus[currentField] = 'completed';
						fieldStatus = { ...fieldStatus };
						await moveToNextField(currentField);
					}
					chatFlow = [...chatFlow];
					await tick();
					scrollToBottom();
					return;
				}
			} else {
				// Editing mode or multi-field processing
				let processedFields = 0;
				let responseMessage = aiResult.response || '';
				let hasValidationErrors = false;

				for (const [fieldName, fieldValue] of Object.entries(aiResult.extracted_data)) {
					if (fieldValue && fieldValue.trim()) {
						let valueToValidate = fieldValue;
						if (fieldName === 'due_date') {
							const parsedDate = parseDate(fieldValue);
							if (parsedDate) {
								valueToValidate = parsedDate;
							}
						}

						const validation = validateField(fieldName, valueToValidate);
						if (typeof validation === 'string') {
							hasValidationErrors = true;
							responseMessage += `\n\n⚠️ ${fieldConfig[fieldName]?.name || fieldName}: ${validation}`;
						} else if (validation.valid) {
							formData[fieldName] = validation.correctedValue;
							processedFields++;
						}
					}
				}

				if (processedFields > 0 && !hasValidationErrors) {
					updateFieldStatus();
					editingField = null;
					const nextField = getNextField();
					if (nextField) {
						const fieldInfo = fieldConfig[nextField];
						responseMessage += `\n\n${fieldInfo?.description || 'Please provide ' + nextField}`;
						currentField = nextField;
					}
				}

				if (responseMessage.trim()) {
					chatFlow.push({ role: 'assistant', content: responseMessage });
				}
			}
		} else {
			// No data extracted - provide guidance or process as single field
			if (aiResult && aiResult.response) {
				chatFlow.push({ role: 'assistant', content: aiResult.response });
			} else {
				// Fallback to simple field processing
				const validation = validateField(currentField, userInput);
				if (typeof validation === 'string') {
					chatFlow.push({ role: 'assistant', content: validation });
				} else if (validation.valid) {
					formData[currentField] = validation.correctedValue;
					formData = { ...formData };
					fieldStatus[currentField] = 'completed';
					fieldStatus = { ...fieldStatus };
					await moveToNextField(currentField);
				}
			}
		}

		chatFlow = [...chatFlow];
		saveChatFlow();
		await tick();
		scrollToBottom();
	}

	// Get next field to fill
	function getNextField() {
		for (const field of ALL_FIELDS) {
			if (!formData[field] || formData[field].trim() === '') {
				return field;
			}
		}
		return null;
	}

	// Enhanced form submission with AI review
	async function submitFormWithAI() {
		const systemPrompt =
			'Review this request form and provide a summary:\n\n' +
			'Form Data:\n' +
			JSON.stringify(formData, null, 2) +
			'\n\n' +
			'Attachments: ' +
			attachments.length +
			' files, ' +
			attachmentUrls.length +
			' URLs\n\n' +
			'Please provide:\n' +
			'1. A brief summary of the request\n' +
			'2. Any missing critical information\n' +
			'3. Suggestions for improvement\n' +
			'4. Overall quality assessment (1-10)\n\n' +
			'Respond in a helpful, professional tone.';

		const messages = [
			{ role: 'system', content: systemPrompt },
			{ role: 'user', content: 'Please review this DB request.' }
		];

		const aiReview = await callOpenAI(messages);

		if (aiReview) {
			chatFlow.push({
				role: 'assistant',
				content:
					'## AI Review\n\n' +
					aiReview +
					'\n\nWould you like to submit this request or make any changes?'
			});
		}

		chatFlow = [...chatFlow];
		saveChatFlow();
		scrollToBottom();
	}

	// Enhanced initialization with AI greeting
	async function initializeWithAI() {
		try {
			const systemPrompt =
				'You are a FAST, FRIENDLY, and INTELLIGENT DB request form assistant. You help users fill out database request forms with natural language understanding.\n\n' +
				'Your capabilities:\n' +
				'- Understand natural language responses\n' +
				'- Fix typos automatically (e.g., "faetrue" → "Feature")\n' +
				'- Provide helpful guidance for each field\n' +
				'- Handle special commands (help, skip, back, summary, clear)\n' +
				'- Extract multiple fields from single responses\n' +
				'- Validate input and suggest corrections\n\n' +
				'Special commands users can use:\n' +
				'- "help" - Get detailed guidance for current field\n' +
				'- "skip" - Skip optional fields\n' +
				'- "back" - Go to previous field\n' +
				'- "summary" - Show form progress\n' +
				'- "clear" - Clear current field\n' +
				'- "edit [field]" - Edit specific field\n\n' +
				'Create a warm, engaging greeting that:\n' +
				'1. Welcomes the user\n' +
				'2. Explains your AI capabilities\n' +
				'3. Mentions the special commands\n' +
				'4. Asks for the request title to start\n' +
				'5. Keeps it conversational and encouraging\n\n' +
				'Example tone: "Hi there! 👋 I\'m your AI-powered DB request assistant. I can understand natural language, fix typos, and guide you through the form. Just tell me about your request in your own words!\n\n' +
				'💡 Quick Tips:\n' +
				'• Say "help" for field guidance\n' +
				'• Say "summary" to see your progress\n' +
				'• Say "back" to edit previous fields\n' +
				'• Say "skip" for optional fields\n\n' +
				"Let's start with the request title - what would you like to call this request?";

			const messages = [
				{ role: 'system', content: systemPrompt },
				{ role: 'user', content: 'Start the DB request form.' }
			];

			const aiGreeting = await callOpenAI(messages);

			if (aiGreeting) {
				chatFlow.push({
					role: 'assistant',
					content: aiGreeting
				});
			} else {
				// Fallback to rule-based greeting
				showFallbackMessage();
				return;
			}
		} catch (error) {
			console.error('AI initialization error:', error);
			// Fallback to rule-based greeting
			showFallbackMessage();
			return;
		}

		chatFlow = [...chatFlow];
		saveChatFlow();
		currentField = 'title';
	}

	// Initialize with AI when component mounts (only once)
	let aiInitialized = false;
	$: if (chatFlow.length === 0 && !aiInitialized) {
		aiInitialized = true;
		// Use fallback message to avoid double greeting
		showFallbackMessage();
		currentField = 'title';
	}

	// Fallback message if AI is not available
	async function showFallbackMessage() {
		const fallbackMessage =
			"Hello! 👋 I'm here to help you fill out the DB Request Form.\n\n" +
			"Since AI features are currently unavailable, I'll guide you through the form using traditional validation rules.\n\n" +
			'💡 Quick Tips:\n' +
			'• Say "help" for field guidance\n' +
			'• Say "summary" to see your progress  \n' +
			'• Say "back" to edit previous fields\n' +
			'• Say "skip" for optional fields\n' +
			'• Say "clear" to clear current field\n\n' +
			'Let\'s start with the first field: Title. Please provide a descriptive title for your database request (e.g., "User Management System Enhancement").';

		chatFlow.push({ role: 'assistant', content: fallbackMessage });
		chatFlow = [...chatFlow];
		saveChatFlow();
		scrollToBottom();
	}

	// Enhanced helper functions for AI-powered features
	async function showFieldHelp() {
		const currentFieldInfo = fieldConfig[currentField];
		const requirements = getFieldRequirements(currentField);
		const examples = getFieldExamples(currentField);
		const isRequired = isFieldRequired(currentField);

		let helpMessage =
			'## 📋 Help for ' +
			currentFieldInfo.name +
			'\n\n' +
			(isRequired ? '🔴 Required Field' : '🟡 Optional Field') +
			'\n\n' +
			'What is this field?\n' +
			currentFieldInfo.description +
			'\n\n' +
			'Requirements:\n' +
			requirements +
			'\n\n' +
			'Examples:\n' +
			examples +
			'\n\n' +
			'Current Progress:* ' +
			completionPercentage +
			'% complete\n\n' +
			'Available Commands:\n' +
			'• Type "skip" to skip this field ' +
			(isRequired ? '(not available for required fields)' : '') +
			'\n' +
			'• Type "back" to go to previous field\n' +
			'• Type "clear" to clear this field\n' +
			'• Type "summary" to see all your answers\n' +
			'• Type "edit [field]" to edit a specific field\n' +
			'• Type "restart" to start over\n' +
			'• Type "cancel" to cancel current operation\n\n' +
			'Note: Your data is not saved between sessions for privacy.\n\n' +
			'Quick Tips:\n' +
			'• You can use natural language (e.g., "This is a bug fix for the login page")\n' +
			"• I'll automatically correct typos and format your input\n" +
			'• You can edit any field later using "edit [field name]"';

		chatFlow.push({ role: 'assistant', content: helpMessage });
		chatFlow = [...chatFlow];
		saveChatFlow();
		scrollToBottom();
	}

	async function goToPreviousField() {
		const currentIndex = ALL_FIELDS.indexOf(currentField);
		if (currentIndex > 0) {
			const previousField = ALL_FIELDS[currentIndex - 1];
			currentField = previousField;
			editingField = previousField;

			const fieldInfo = fieldConfig[previousField];
			chatFlow.push({
				role: 'assistant',
				content:
					"I've moved back to the " +
					(fieldInfo?.name || previousField) +
					' field. Current value: "' +
					(formData[previousField] || 'empty') +
					'". What would you like to change it to?'
			});
		} else {
			chatFlow.push({
				role: 'assistant',
				content:
					"You're already at the first field (" +
					(fieldConfig[currentField]?.name || currentField) +
					').'
			});
		}

		chatFlow = [...chatFlow];
		saveChatFlow();
		scrollToBottom();
	}

	async function clearCurrentField() {
		if (editingField) {
			formData[editingField] = '';
			updateFieldStatus();
			chatFlow.push({
				role: 'assistant',
				content:
					"I've cleared the " +
					(fieldConfig[editingField]?.name || editingField) +
					' field. What would you like to set it to?'
			});
		} else {
			formData[currentField] = '';
			updateFieldStatus();
			chatFlow.push({
				role: 'assistant',
				content:
					"I've cleared the " +
					(fieldConfig[currentField]?.name || currentField) +
					' field. Please provide a new value.'
			});
		}

		chatFlow = [...chatFlow];
		saveChatFlow();
		scrollToBottom();
	}

	async function handleSkipField() {
		const currentFieldInfo = fieldConfig[currentField];

		// Check if field is required
		if (isFieldRequired(currentField)) {
			chatFlow.push({
				role: 'assistant',
				content:
					'The ' +
					currentFieldInfo?.name +
					' field is required and cannot be skipped or set to N/A. Please provide a valid value, or say "help" for guidance.'
			});
		} else {
			formData[currentField] = 'N/A';
			updateFieldStatus();
			const nextField = getNextField();
			if (nextField) {
				const nextFieldInfo = fieldConfig[nextField];
				chatFlow.push({
					role: 'assistant',
					content:
						"I've marked " + currentFieldInfo?.name + ' as N/A. ' + nextFieldInfo?.description + ' '
				});
				currentField = nextField;
			} else {
				chatFlow.push({
					role: 'assistant',
					content:
						'Great! All fields are complete. Would you like to review your request or submit it?'
				});
			}
		}
		chatFlow = [...chatFlow];
		scrollToBottom();
	}

	// Helper functions for field requirements and examples
	function getFieldRequirements(field) {
		const requirements = {
			title:
				'• Must be descriptive (3+ characters)\n• Professional and clear\n• No excessive emojis or repeated characters',
			type: '• Must be one of: Feature, Bug, or Improvement\n• Case-insensitive',
			description:
				'• Must be detailed (15+ characters)\n• Explain what you need and why\n• Be specific about requirements\n• No gibberish or meaningless text',
			priority:
				"• Must be one of:\n  - 0 or 'Critical' (urgent, blocking work)\n  - 1 or 'High' (important, needs attention soon)\n  - 2 or 'Medium' (normal priority)\n  - 3 or 'Low' (nice to have, not urgent)",
			owner: "• Full name of the person responsible\n• Must be a real person's name",
			created_by: "• Full name of the person creating this request\n• Must be a real person's name",
			client: '• Client or business unit name\n• Can be skipped if not applicable'
		};
		return requirements[field] || '• Provide relevant information';
	}

	function getFieldExamples(field) {
		const examples = {
			title:
				"• 'User Analytics Dashboard Access'\n• 'Database Performance Optimization'\n• 'Customer Data Export Feature'",
			type: "• 'Feature' (new functionality)\n• 'Bug' (fixing an issue)\n• 'Improvement' (enhancing existing feature)",
			description:
				"• 'The analytics team needs read access to customer data tables for generating monthly reports'\n• 'We need to optimize database queries to reduce response time from 5s to under 1s'",
			priority:
				"• '0' or 'Critical' (urgent, blocking work)\n• '1' or 'High' (important, needs attention soon)\n• '2' or 'Medium' (normal priority)\n• '3' or 'Low' (nice to have, not urgent)",
			owner: "• 'John Smith'\n• 'Sarah Johnson'\n• 'Mike Chen'",
			created_by: "• 'Anupama Rajamohan'\n• 'Your full name'",
			client: "• 'Analytics Team'\n• 'Marketing Department'\n• 'Customer Success'\n• 'Ajio'"
		};
		return examples[field] || '• Provide a relevant example';
	}

	function isFieldRequired(field) {
		const requiredFields = ['title', 'type', 'description', 'priority', 'owner', 'created_by'];
		return requiredFields.includes(field);
	}

	// New function to check which fields need changes
	function checkFieldsForChanges() {
		const fieldsNeedingChanges = [];
		const fieldsNeedingReview = [];

		// Check each field for issues
		ALL_FIELDS.forEach((field) => {
			const value = formData[field];
			const fieldInfo = fieldConfig[field];

			// Check for empty required fields
			if (isFieldRequired(field) && (!value || value.trim() === '')) {
				fieldsNeedingChanges.push({
					field: field,
					name: fieldInfo.name,
					issue: 'Missing required field',
					severity: 'critical'
				});
				return;
			}

			// Check for N/A values in required fields
			if (isFieldRequired(field) && value === 'N/A') {
				fieldsNeedingChanges.push({
					field: field,
					name: fieldInfo.name,
					issue: 'Required field cannot be N/A',
					severity: 'critical'
				});
				return;
			}

			// Check for TBD values in optional fields
			if (value === 'TBD' && !isFieldRequired(field)) {
				fieldsNeedingReview.push({
					field: field,
					name: fieldInfo.name,
					issue: 'Set to TBD - consider providing a value',
					severity: 'warning'
				});
			}

			// Field-specific validations
			if (field === 'title' && value) {
				if (value.length < 5) {
					fieldsNeedingChanges.push({
						field: field,
						name: fieldInfo.name,
						issue: 'Title is too short (minimum 5 characters)',
						severity: 'warning'
					});
				}
			}

			if (field === 'description' && value) {
				if (value.length < 15) {
					fieldsNeedingChanges.push({
						field: field,
						name: fieldInfo.name,
						issue: 'Description is too short (minimum 15 characters)',
						severity: 'warning'
					});
				}

				// Check for vague descriptions
				const vagueWords = ['same', 'usual', 'fix', 'improve', 'enhance', 'update'];
				const hasVagueContent = vagueWords.some((word) => value.toLowerCase().includes(word));

				if (hasVagueContent && value.length < 30) {
					fieldsNeedingChanges.push({
						field: field,
						name: fieldInfo.name,
						issue: 'Description could be more specific',
						severity: 'warning'
					});
				}
			}

			if (field === 'due_date' && value) {
				// Check if due date is in the past
				const dueDate = dayjs(value);
				if (dueDate.isBefore(dayjs(), 'day')) {
					fieldsNeedingChanges.push({
						field: field,
						name: fieldInfo.name,
						issue: 'Due date is in the past',
						severity: 'critical'
					});
				}
			}

			if (field === 'priority' && value) {
				// Check if priority is valid
				const validPriorities = ['0 - Critical', '1 - High', '2 - Medium', '3 - Low'];
				if (!validPriorities.includes(value)) {
					fieldsNeedingChanges.push({
						field: field,
						name: fieldInfo.name,
						issue: 'Invalid priority value',
						severity: 'critical'
					});
				}
			}

			if (field === 'type' && value) {
				// Check if type is valid
				const validTypes = ['Feature', 'Bug', 'Improvement'];
				if (!validTypes.includes(value)) {
					fieldsNeedingChanges.push({
						field: field,
						name: fieldInfo.name,
						issue: 'Invalid type value',
						severity: 'critical'
					});
				}
			}

			// Check for very short names in name fields
			if ((field === 'owner' || field === 'created_by') && value) {
				if (value.length < 2) {
					fieldsNeedingChanges.push({
						field: field,
						name: fieldInfo.name,
						issue: 'Name is too short (minimum 2 characters)',
						severity: 'warning'
					});
				}
			}
		});

		return {
			fieldsNeedingChanges,
			fieldsNeedingReview,
			hasIssues: fieldsNeedingChanges.length > 0 || fieldsNeedingReview.length > 0
		};
	}

	// New function to extract multiple fields from a single input
	function extractMultipleFields(userInput) {
		const extracted = {};
		const lowerInput = userInput.toLowerCase();

		// Extract type - make it more specific to avoid false matches
		const typePatterns = [
			/(?:type is|type\s+is)\s+(feature|bug|improvement)/i,
			/(?:it is|its)\s+(feature|bug|improvement)/i,
			/\b(feature|bug|improvement)\b/i
		];

		for (const pattern of typePatterns) {
			const match = lowerInput.match(pattern);
			if (match) {
				const type = match[1].toLowerCase();
				if (type === 'feature') extracted.type = 'Feature';
				else if (type === 'bug') extracted.type = 'Bug';
				else if (type === 'improvement') extracted.type = 'Improvement';
				break;
			}
		}

		// Extract priority - make it more specific
		const priorityPatterns = [
			/(?:the\s+)?priority\s+is\s+(high|medium|low|critical|urgent)/i,
			/(?:priority|it is|level)\s+(high|medium|low|critical|urgent)/i,
			/(high|medium|low|critical|urgent)\s+(?:priority|level)/i,
			/\b(high|medium|low|critical|urgent)\b/i,
			/priority\s+(\d+)/i,
			/\b(\d+)\s+(?:priority|level)/i
		];

		for (const pattern of priorityPatterns) {
			const match = lowerInput.match(pattern);
			if (match) {
				const priority = match[1].toLowerCase();
				if (priority === 'critical' || priority === 'urgent' || priority === '0')
					extracted.priority = '0 - Critical';
				else if (priority === 'high' || priority === '1') extracted.priority = '1 - High';
				else if (priority === 'medium' || priority === '2') extracted.priority = '2 - Medium';
				else if (priority === 'low' || priority === '3') extracted.priority = '3 - Low';
				break;
			}
		}

		// Extract created_by - make it more specific to avoid false matches
		const createdByPatterns = [
			/(?:created by|created\s+by)\s+([a-zA-Z]+)/i,
			/(?:by)\s+([a-zA-Z]+)(?:\s|$)/i // Add word boundary to avoid matching "by next"
		];

		for (const pattern of createdByPatterns) {
			const match = lowerInput.match(pattern);
			if (match) {
				// Don't extract if it's part of a date phrase
				const extractedName = match[1].toLowerCase();
				if (!['next', 'last', 'this', 'tomorrow', 'today'].includes(extractedName)) {
					extracted.created_by = match[1].charAt(0).toUpperCase() + match[1].slice(1);
				}
				break;
			}
		}

		// Extract owner - make it more specific
		const ownerPatterns = [
			/(?:owner is|owner\s+is)\s+([a-zA-Z]+)/i,
			/(?:owner)\s+([a-zA-Z]+)(?:\s|$)/i // Add word boundary
		];

		for (const pattern of ownerPatterns) {
			const match = lowerInput.match(pattern);
			if (match) {
				// Don't extract if it's part of a date phrase
				const extractedName = match[1].toLowerCase();
				if (!['next', 'last', 'this', 'tomorrow', 'today'].includes(extractedName)) {
					extracted.owner = match[1].charAt(0).toUpperCase() + match[1].slice(1);
				}
				break;
			}
		}

		// Extract due_date - improve patterns to catch more variations
		const dueDatePatterns = [
			/(?:due date|due\s+date|due by)\s+(.+?)(?:\s|,|$)/i,
			/(?:by)\s+(next week|next month|next \w+|tomorrow|today|in \d+ days?)/i,
			/(?:due date|due\s+date|due by)\s+(next week|next month|next \w+|tomorrow|today|in \d+ days?)/i,
			/(?:is by)\s+(next week|next month|next \w+|tomorrow|today|in \d+ days?)/i
		];

		for (const pattern of dueDatePatterns) {
			const match = lowerInput.match(pattern);
			if (match) {
				extracted.due_date = match[1].trim();
				break;
			}
		}

		// Extract client - make it more specific
		const clientPatterns = [
			/(?:client is|client\s+is)\s+([a-zA-Z]+)/i,
			/(?:client)\s+([a-zA-Z]+)(?:\s|$)/i // Add word boundary
		];

		for (const pattern of clientPatterns) {
			const match = lowerInput.match(pattern);
			if (match) {
				// Don't extract if it's part of a date phrase
				const extractedName = match[1].toLowerCase();
				if (!['next', 'last', 'this', 'tomorrow', 'today'].includes(extractedName)) {
					extracted.client = match[1].charAt(0).toUpperCase() + match[1].slice(1);
				}
				break;
			}
		}

		return extracted;
	}

	// Enhanced fallback rule-based processing

	// Helper to prompt for the current field
	function promptCurrentField() {
		const fieldInfo = fieldConfig[currentField];
		let prompt = '';
		if (currentField === 'title')
			prompt = 'What is the title of your DB request? Please provide a clear, descriptive name.';
		else if (currentField === 'type')
			prompt = 'What type of request is this? Options: ' + fieldInfo.options.join(', ');
		else if (currentField === 'client')
			prompt = 'Who is the client or business unit requesting this?';
		else if (currentField === 'module')
			prompt = 'Which module or specific part of the system does this relate to?';
		else if (currentField === 'description')
			prompt =
				'Please describe the requirement in detail. Include specific details about what needs to be implemented or fixed. Minimum 15 characters.';
		else if (currentField === 'priority')
			prompt =
				'What is the priority level? Enter 0 for Critical, 1 for High, 2 for Medium, or 3 for Low. You can also type the word (e.g., "critical").';
		else if (currentField === 'due_date')
			prompt =
				'What is the expected completion or delivery date? (e.g., 2025-07-20 or "next week")';
		else if (currentField === 'reference_link')
			prompt =
				'Do you have any reference links or URLs related to this request? (If not applicable, type "skip", "n/a", or "none")';
		else if (currentField === 'owner')
			prompt =
				'Who will be the owner responsible for this request? (Type a name to see matching suggestions)';
		else if (currentField === 'created_by')
			prompt = 'Who is creating this request? (Type a name to see matching suggestions)';
		chatFlow.push({ role: 'assistant', content: prompt });
		chatFlow = [...chatFlow];
		saveChatFlow();
		scrollToBottom();
	}
</script>

<div class="w-full min-h-screen h-full flex flex-row bg-gray-50 dark:bg-gray-850">
	<!-- Left: Chat Conversation -->
	<div class="flex-1 flex flex-col h-full">
		<!-- Header -->
		<div
			class="pointer-events-auto z-20 flex justify-between items-center p-2.5 font-primary text-gray-900 dark:text-white border-b border-gray-200 dark:border-gray-700"
		>
			<button
				class="self-center pointer-events-auto p-1 rounded-full bg-white dark:bg-gray-850 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
				on:click={() => {
					showArtifacts.set(false);
				}}
			>
				<ArrowLeft className="size-3.5 text-gray-900 dark:text-white" />
			</button>
			<div class="flex-1 flex items-center justify-center">
				<h2 class="text-lg font-medium">DB Request Form</h2>
			</div>
			<div class="flex items-center gap-2">
				<button
					class="self-center pointer-events-auto p-1 rounded-full bg-white dark:bg-gray-850 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
					title="Reset Form"
					on:click={resetForm}
				>
					<Refresh className="size-3.5 text-gray-900 dark:text-white" />
				</button>
				<button
					class="self-center pointer-events-auto p-1 rounded-full bg-white dark:bg-gray-850 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
					on:click={() => {
						dispatch('close');
						showControls.set(false);
						showArtifacts.set(false);
					}}
				>
					<XMark className="size-3.5 text-gray-900 dark:text-white" />
				</button>
			</div>
		</div>
		{#if overlay}
			<div class="absolute top-0 left-0 right-0 bottom-0 z-10"></div>
		{/if}
		<!-- Conversation -->
		<div class="flex-1 overflow-y-auto p-4" bind:this={chatContainer}>
			{#if chatFlow.length === 0}
				<div class="flex items-center justify-center h-full">
					<div class="text-center text-gray-500 dark:text-gray-400">
						The assistant will guide you through the form.
					</div>
				</div>
			{:else}
				<div class="space-y-4">
					{#each chatFlow as message}
						<div class="flex {message.role === 'user' ? 'justify-end' : 'justify-start'}">
							<div
								class="max-w-[80%] {message.role === 'user'
									? 'bg-blue-500 text-white'
									: 'bg-white dark:bg-gray-800'} rounded-lg p-3 shadow-sm"
							>
								<div class="text-sm whitespace-pre-wrap">
									{@html message.content.replace(/\n/g, '<br>')}
								</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
		<!-- Input Area -->
		<div class="p-4 border-t border-gray-200 dark:border-gray-700">
			<form on:submit|preventDefault={handleUserSubmit} class="flex gap-2">
				<input
					id="artifact-form-input"
					type="text"
					bind:value={userInput}
					placeholder={state === 'editing'
						? 'Enter new value...'
						: state === 'review'
							? 'Type Submit, Edit [field], or Cancel...'
							: 'Type your response...'}
					class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
					disabled={loading || state === 'done'}
					on:focus={() => {}}
					on:input={(e) => {
						const inputValue = e.target.value;

						// Don't clear suggestions while typing - let them stay visible
						// Suggestions will only be cleared when user makes a selection
					}}
				/>
				<button
					type="submit"
					class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition disabled:opacity-50"
					disabled={isProcessing || !userInput.trim() || loading || state === 'done'}
				>
					{loading ? 'Submitting...' : 'Continue'}
				</button>
			</form>
		</div>
	</div>
	<!-- Right: Progress Tracker -->
	<div
		class="w-80 min-w-[320px] max-w-[320px] bg-white dark:bg-gray-800 p-4 border-l-4 border-blue-400 dark:border-blue-600 h-full flex flex-col"
		style="box-shadow: 0 0 0 4px #60a5fa33; overflow-y: auto; max-height: 100vh;"
	>
		<!-- Progress Tracker Panel -->
		<div class="mb-6">
			<h3 class="text-lg font-medium mb-2">Progress Tracker</h3>
			<div class="flex items-center gap-2 mb-2">
				<div class="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
					<div
						class="bg-green-500 h-2 rounded-full transition-all duration-300"
						style="width: {completionPercentage}%"
					></div>
				</div>
				<span class="text-sm font-medium">{completionPercentage}%</span>
			</div>
			<div class="text-sm text-gray-600 dark:text-gray-400">
				{Object.values(fieldStatus).filter((status) => status === 'completed').length} of {TOTAL_FIELDS}
				fields completed
				{#if Object.values(fieldStatus).filter((status) => status === 'skipped').length > 0}
					| {Object.values(fieldStatus).filter((status) => status === 'skipped').length} skipped
				{/if}
				{#if Object.values(fieldStatus).filter((status) => status === 'need_review').length > 0}
					| {Object.values(fieldStatus).filter((status) => status === 'need_review').length} need review
				{/if}
			</div>
		</div>
		<div class="space-y-3 flex-1">
			{#each ALL_FIELDS as fieldKey}
				{@const field = fieldConfig[fieldKey]}
				{@const status = fieldStatus[fieldKey]}
				{@const StatusIcon = getStatusIcon(status)}
				{@const value = formData[fieldKey]}
				{@const isEditing = editingField === fieldKey}
				<div
					class="p-3 rounded-lg border {getStatusBgColor(
						status
					)} border-gray-200 dark:border-gray-700 {isEditing ? 'ring-2 ring-blue-500' : ''}"
				>
					<div class="flex items-start gap-3">
						{#if StatusIcon}
							<StatusIcon className="size-5 mt-0.5 {getStatusColor(status)}" />
						{:else if status === 'skipped'}
							<span class="size-5 mt-0.5 inline-block align-middle text-yellow-500">🟡</span>
						{:else if status === 'need_review'}
							<span class="size-5 mt-0.5 inline-block align-middle text-yellow-500">🟡</span>
						{:else if status === 'pending'}
							<span class="size-5 mt-0.5 inline-block align-middle text-yellow-500">•</span>
						{:else if status === 'warning'}
							<span class="size-5 mt-0.5 inline-block align-middle text-yellow-500">⚠</span>
						{/if}
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2 mb-1">
								<span class="text-sm font-medium text-gray-900 dark:text-white">
									{field.icon}
									{field.name}
									{#if isEditing}
										<span
											class="text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 px-2 py-0.5 rounded-full ml-2"
										>
											Editing
										</span>
									{/if}
								</span>
								{#if status === 'completed'}
									<span
										class="text-xs bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 px-2 py-0.5 rounded-full"
									>
										Complete
									</span>
								{:else if status === 'skipped'}
									<span
										class="text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-0.5 rounded-full"
									>
										🟡 Skipped
									</span>
								{:else if status === 'need_review'}
									<span
										class="text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-0.5 rounded-full"
									>
										🟡 Need Review
									</span>
								{:else if status === 'warning'}
									<span
										class="text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-0.5 rounded-full"
									>
										Needs Review
									</span>
								{:else}
									<span
										class="text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-0.5 rounded-full"
									>
										Pending
									</span>
								{/if}
							</div>
							<div class="text-xs text-gray-600 dark:text-gray-400 mb-2">
								{field.description}
							</div>
							{#if value && status === 'completed'}
								<div
									class="text-sm text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded"
								>
									{value}
								</div>
							{/if}
						</div>
					</div>
				</div>
			{/each}

			<!-- Attachments Field -->
			{#if true}
				{@const hasAttachments = attachments.length > 0 || attachmentUrls.length > 0}
				{@const attachmentStatus = hasAttachments ? 'completed' : 'pending'}
				{@const AttachmentStatusIcon = getStatusIcon(attachmentStatus)}
				<div
					class="p-3 rounded-lg border {getStatusBgColor(
						attachmentStatus
					)} border-gray-200 dark:border-gray-700"
				>
					<div class="flex items-start gap-3">
						{#if AttachmentStatusIcon}
							<AttachmentStatusIcon className="size-5 mt-0.5 {getStatusColor(attachmentStatus)}" />
						{:else if attachmentStatus === 'pending'}
							<span class="size-5 mt-0.5 inline-block align-middle text-yellow-500">•</span>
						{/if}
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2 mb-1">
								<span class="text-sm font-medium text-gray-900 dark:text-white">
									📎 Attachments
								</span>
								{#if attachmentStatus === 'completed'}
									<span
										class="text-xs bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 px-2 py-0.5 rounded-full"
									>
										Complete
									</span>
								{:else}
									<span
										class="text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-0.5 rounded-full"
									>
										Optional
									</span>
								{/if}
							</div>
							<div class="text-xs text-gray-600 dark:text-gray-400 mb-2">
								Files, images, or URLs to include with your request
							</div>
							{#if hasAttachments}
								<div
									class="text-sm text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded"
								>
									{attachments.length > 0 ? attachments.length + ' file(s)' : ''}
									{attachments.length > 0 && attachmentUrls.length > 0 ? ', ' : ''}
									{attachmentUrls.length > 0 ? attachmentUrls.length + ' URL(s)' : ''}
								</div>
							{/if}
						</div>
					</div>
				</div>
			{/if}
		</div>
		{#if completionPercentage === 100}
			<div
				class="mt-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg"
			>
				<div class="flex items-center gap-2 mb-2">
					<Check className="size-5 text-green-500" />
					<span class="font-medium text-green-800 dark:text-green-200">All fields completed!</span>
				</div>
				<div class="text-sm text-green-700 dark:text-green-300">
					Your DB request is ready for review.
				</div>
			</div>
		{:else if completionPercentage >= 80}
			<div
				class="mt-6 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg"
			>
				<div class="flex items-center gap-2 mb-2">
					<span class="text-yellow-500">⚠</span>
					<span class="font-medium text-yellow-800 dark:text-yellow-200">Almost complete!</span>
				</div>
				<div class="text-sm text-yellow-700 dark:text-yellow-300">
					Some fields may need improvement. Please review the warnings above.
				</div>
			</div>
		{/if}

		{#if lastError}
			<div
				class="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg"
			>
				<div class="flex items-center gap-2 mb-2">
					<span class="text-red-500">⚠</span>
					<span class="font-medium text-red-800 dark:text-red-200 text-sm">Last Error</span>
				</div>
				<div class="text-xs text-red-700 dark:text-red-300">
					{lastError.message}
				</div>
				<div class="text-xs text-red-600 dark:text-red-400 mt-1">
					Attempts: {submissionAttempts} | Time: {new Date(
						lastError.timestamp
					).toLocaleTimeString()}
				</div>
			</div>
		{/if}
		<!-- Attachment Controls -->
		<div class="mt-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
			<div class="flex items-center gap-2 mb-2">
				<button
					type="button"
					class="p-2 rounded-full bg-blue-100 hover:bg-blue-200 text-blue-600"
					on:click={() => (showAttachmentInput = !showAttachmentInput)}
					title="Add Attachment"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						class="w-5 h-5"
						><path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.586-6.586a4 4 0 10-5.656-5.656l-6.586 6.586"
						/></svg
					>
				</button>
				<span class="text-sm font-medium">Add Attachments</span>
				<label class="ml-2 px-2 py-1 bg-blue-500 text-white rounded cursor-pointer text-xs">
					<input
						type="file"
						multiple
						accept=".png,.jpg,.jpeg,.csv,.xls,.xlsx,.pdf"
						on:change={handleFileChange}
						style="display:none"
					/>
					Choose File(s)
				</label>
			</div>
			{#if showAttachmentInput}
				<div class="flex flex-col gap-2 mb-2">
					<div class="flex gap-2">
						<input
							type="text"
							class="flex-1 px-2 py-1 border rounded text-xs"
							placeholder="Paste public URL..."
							bind:value={attachmentUrlInput}
						/>
						<button
							type="button"
							class="px-2 py-1 bg-blue-500 text-white rounded text-xs"
							on:click={handleAddUrl}>Add URL</button
						>
					</div>
				</div>
			{/if}
			{#if attachments.length > 0}
				<div class="mb-2">
					{#each attachments as file, idx}
						{@const uploadStatus = attachmentUploadStatus[file.name]}
						<div
							class="flex items-center gap-2 text-xs bg-gray-100 dark:bg-gray-700 rounded px-2 py-1 mb-1"
						>
							{#if file.type.startsWith('image/')}
								<img
									src={URL.createObjectURL(file)}
									alt={file.name}
									class="h-8 w-8 object-cover rounded"
								/>
							{/if}
							<span class="flex-1">{file.name}</span>
							{#if uploadStatus}
								<span
									class="text-xs {uploadStatus.status === 'success'
										? 'text-green-600'
										: 'text-red-600'}"
								>
									{uploadStatus.status === 'success' ? '✅' : '❌'}
								</span>
							{/if}
							<a
								href={URL.createObjectURL(file)}
								download={file.name}
								class="text-blue-500 underline ml-1">Download</a
							>
							<button type="button" class="text-red-500" on:click={() => removeAttachment(idx)}
								>&times;</button
							>
						</div>
					{/each}
				</div>
			{/if}
			{#if attachmentUrls.length > 0}
				<div class="mb-2">
					{#each attachmentUrls as url, idx}
						<div
							class="flex items-center gap-2 text-xs bg-gray-100 dark:bg-gray-700 rounded px-2 py-1 mb-1"
						>
							<a href={url} target="_blank" class="text-blue-500 underline">{url}</a>
							<button type="button" class="text-red-500" on:click={() => removeAttachmentUrl(idx)}
								>&times;</button
							>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>
