export namespace main {
	
	export class MonthGoal {
	    id: string;
	    goal: string;
	
	    static createFrom(source: any = {}) {
	        return new MonthGoal(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.id = source["id"];
	        this.goal = source["goal"];
	    }
	}
	export class TimeBlock {
	    id: string;
	    date: string;
	    startHour: number;
	    startMinute: number;
	    duration: number;
	    title: string;
	    color: string;
	
	    static createFrom(source: any = {}) {
	        return new TimeBlock(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.id = source["id"];
	        this.date = source["date"];
	        this.startHour = source["startHour"];
	        this.startMinute = source["startMinute"];
	        this.duration = source["duration"];
	        this.title = source["title"];
	        this.color = source["color"];
	    }
	}
	export class WeekTask {
	    id: string;
	    content: string;
	    done: boolean;
	
	    static createFrom(source: any = {}) {
	        return new WeekTask(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.id = source["id"];
	        this.content = source["content"];
	        this.done = source["done"];
	    }
	}

}

