import handler from '../../api/diario.js';
import { adaptar } from '../_vercel.js';
export const onRequest = adaptar(handler);
