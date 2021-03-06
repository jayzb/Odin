from time import sleep
from ..utilities.params import Events, verbosity_dict, Verbosities


class Fund(object):
    """Fund Class

    The fund object is responsible for combining portfolios and strategies with
    data handlers and execution handlers in a manner that allows for either live
    or simulated trading. The fund ensures that new data is streamed and that
    signal events are generated, order events are placed, and that fill events
    are processed according to the most recent data provided by the data
    handler.

    The fund object is also responsible for rebalancing portfolios according to
    a specified timeline.

    Parameters
    ----------
    data_handler: Object inheriting from the abstract data handler class.
        This object supplies the data to update the prices of held positions and
        provide new bar data with which to construct features.
    execution_handler: Object inheriting from the execution handler class.
        The execution handler is responsible for executing trades as they are
        placed by the portfolio object.
    fund_handler: Fund handler object.
        The fund handler rebalances the portfolio when requested and performs
        other administrative actions on the level of the fund.
    delay: Float
        The number of seconds that should elapse before the fund queries the
        market for the latest bar data.
    verbosity_level: Integer (Optional)
        Determines the amount of I/O generated for logging and debugging
        purposes.
    """
    def __init__(
            self, data_handler, execution_handler, fund_handler, delay,
            verbosity_level=0
    ):
        """Initialize parameters of the fund object."""
        self.data_handler = data_handler
        self.execution_handler = execution_handler
        self.fund_handler = fund_handler
        self.delay = delay
        # Set the verbosity parameter that will control the amount of output to
        # the standard out.
        self.verbosity_level = verbosity_level

    def trade(self):
        """Trade using the strategy in either a backtest or live-trading
        envioronment. This function is executed when a fund object has been
        constructed from underlying portfolio, strategy, data handler, and
        execution handler objects. It actually permits events to be streamed and
        interpreted in proper order.
        """
        # Create shortened variable names for convenience.
        dh = self.data_handler
        eh = self.execution_handler
        fh = self.fund_handler
        events = dh.events
        ports, strats = fh.portfolios, fh.strategies
        port_dict = {p.portfolio_handler.portfolio_id: p for p in ports}

        # Sit in a while loop and await new market data or a cease-and-desist
        # indicator is recognized.
        while True:
            # Request pricing data.
            dh.request_prices()
            # Perform trading until the data handler signals that bar data has
            # been exhausted.
            if not dh.continue_trading:
                break

            # Process events generated by the latest market data. We also check
            # event type to ensure that events are properly handled by functions
            # meant to process that kind of event.
            while not events.empty():
                e = events.get(False)
                e_type = e.event_type

                if e_type == Events.market:
                    # Because the strategy object will sometimes make use of
                    # holdings information, we should first update the
                    # portfolio before generating signals.
                    for s, p in zip(strats, ports):
                        p.process_market_event(e)
                        s.generate_signals()

                    # Check for a rebalance or management event.
                    self.fund_handler.process_market_event(e)
                elif e_type == Events.signal:
                    port_dict[e.portfolio_id].process_signal_event(e)
                elif e_type == Events.order:
                    eh.execute_order(e)
                elif e_type == Events.fill:
                    port_dict[e.portfolio_id].process_fill_event(e)
                elif e_type == Events.rebalance:
                    self.fund_handler.rebalance()
                elif e_type == Events.management:
                    self.fund_handler.manage()
                else:
                    raise ValueError("Invalid event type: {}".format(e_type))

                # Control I/O.
                if verbosity_dict[e_type] <= self.verbosity_level:
                    print(e)

            else:
                # Perform processing after all of the time periods events have
                # been processed.
                for p in ports:
                    p.process_post_events()
                    if Verbosities.portfolio.value <= self.verbosity_level:
                        print(p.portfolio_handler.state)

                # Update the historical price record.
                dh.update()

            # Delay the acquisition of new market data.
            if self.delay > 0:
                sleep(self.delay)

