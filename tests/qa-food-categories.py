import sys
sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app'))
from categories import recipe_category
foods=['구운 고기','샤와르마','미트 파르미자나','흰살생선 뫼니에르','부야베스','메기 피시 앤 칩스','카레라이스','토마토 리소토','미트 포트파이','호박 파이','달콤쌉쌀 푸딩','넛츠 초코 비스킷','농어 매운탕','금은 매운탕','송어 파피요트','바삭한 초코 카나페','파이크퍼치 필레 리소토','토마토 크림 생선 커넬']
for name in foods:
 assert recipe_category(name,'craft')=='음식', name
assert recipe_category('수리한 나침반','craft')=='기타'
assert recipe_category('캠프파이어 키트','craft')=='도구'
assert recipe_category('카레라이스','craft',{'recipe':{'카레라이스':'사용자 분류'}})=='사용자 분류'
print('PASS 18 previously unclassified foods, non-food exclusions, custom override priority')
