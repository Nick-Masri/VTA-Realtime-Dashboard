def initGridPricingModel(numDays):
    gridPowPrice = []
    for t in range(96):
        minutes = 15 * t
        if (minutes > 12 * 60) and (minutes <= 18 * 60):
            gridPowPrice.append(.59002)
        elif (minutes > 8.5 * 60) and (minutes <= 12 * 60):
            gridPowPrice.append(.29319)
        elif (minutes > 18 * 60) and (minutes <= 21.5 * 60):
            gridPowPrice.append(.29319)
        else:
            gridPowPrice.append(.22161)
            
    return gridPowPrice

# gridPowPrice = initGridPricingModel(D)