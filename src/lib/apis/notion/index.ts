import { WEBUI_API_BASE_URL } from '$lib/constants';

export type FeatureRequestData = {
	title: string;
	type: string;
	client: string;
	module: string;
	description: string;
	owner: string;
	priority: string;
	due_date: string;
	reference_link?: string;
	attachments?: string[];
	attachment_urls?: string[];
};

export type NameSuggestionRequest = {
	partial_name: string;
	limit?: number;
};

export type NameSuggestionResponse = {
	suggestions: Array<{
		id: string;
		name: string;
		email: string;
		score: number;
		display: string;
	}>;
	total_found: number;
};

export type UserMatchRequest = {
	name: string;
};

export type UserMatchResponse = {
	found: boolean;
	user?: {
		id: string;
		name: string;
		email: string;
		display: string;
	};
	confidence_score?: number;
	suggestions?: Array<{
		id: string;
		name: string;
		email: string;
		score: number;
		display: string;
	}>;
};

export const createFeatureRequest = async (
	token: string,
	data: FeatureRequestData,
	files?: File[]
) => {
	let error = null;

	// Create FormData for file upload
	const formData = new FormData();

	// Add the JSON data as a string
	formData.append('form_data', JSON.stringify(data));

	// Add files if any
	if (files && files.length > 0) {
		files.forEach((file) => {
			formData.append('files', file);
		});
	}

	const res = await fetch(`${WEBUI_API_BASE_URL}/notion/feature-request`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			authorization: `Bearer ${token}`
			// Don't set Content-Type for FormData, let the browser set it with boundary
		},
		body: formData
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getNotionConfig = async (token: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/notion/config`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getAllNotionUsers = async (token: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/notion/users/all`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getNameSuggestions = async (
	token: string,
	request: NameSuggestionRequest
): Promise<NameSuggestionResponse> => {
	let error = null;

	// Use the production endpoint (requires authentication)
	const endpoint = `${WEBUI_API_BASE_URL}/notion/users/suggestions`;
	const headers: Record<string, string> = {
		Accept: 'application/json',
		'Content-Type': 'application/json',
		authorization: `Bearer ${token}`
	};

	const res = await fetch(endpoint, {
		method: 'POST',
		headers,
		body: JSON.stringify(request)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const matchUserName = async (
	token: string,
	request: UserMatchRequest
): Promise<UserMatchResponse> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/notion/users/match`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(request)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
