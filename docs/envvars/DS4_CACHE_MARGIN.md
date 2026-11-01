# `DS4_CACHE_MARGIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 専用エンジンの expert cache が、CPU 側にある expert を VRAM に移す条件の倍率を指定します。CPU 側の最も熱い expert の heat が、VRAM 側の最も冷たい expert の heat にこの倍率を掛け、さらに `DS4_CACHE_BONUS` を足した値を超えると、入れ替え候補になります。これは通常の `strata` エンジンではなく、別実行ファイル `strata-dsv41` 内の処理です。

## 値と判定

| 環境の値 | `c_margin` の値 | 判定への影響 |
|---|---:|---|
| 未設定 | `1.25` | 既定倍率を使う |
| 数値文字列 | `std::atof` が変換した値を `float` に変換 | 変換値を倍率に使う |
| 空文字、数値に変換できない文字列 | `0` | 実装上 `atof` の変換結果 0 を倍率に使う |

文字列全体の妥当性検査、エラー通知、clamp はありません。`atof` は先頭から数値として解釈できる部分を変換するため、後続に文字がある値もその部分が採用されます。負値も拒否されず、倍率としてそのまま使われます。従って、0 や負値では入れ替え条件が緩くなり得ます。`NaN` に変換される値では比較が成立せず、入れ替え条件を通りません。

この値は `Impl` のメンバー初期化時に読み取られ、環境値を毎回読むのではなく、その `Impl` インスタンスが保持します。CLI 引数や別設定による上書きはありません。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` で `strata-dsv41` がビルドされている必要があります。この CMake オプションは既定で OFF です。
- エンジンの expert cache が有効である必要があります。既定は有効ですが、`--no-expert-cache` を指定すると無効になります。
- 該当 layer に VRAM の spare slot があり、入れ替え待ちがなく、進行中 swap 数が `DS4_CACHE_INFLIGHT` による上限未満であることが必要です。
- モデルの expert がすべて VRAM に収まる場合は swap 用の条件を満たさず、この margin による入れ替えは起きません。
- cache の tick で CPU 側の使用記録があり、比較する CPU 側と VRAM 側の expert が選ばれる必要があります。

## 実行時の詳細

decode 等の window 完了後に `cache_tick()` が呼ばれ、expert の heat を更新したうえで swap 条件を判定します。heat は各 expert の使用で加算され、256 token ごとに `DS4_CACHE_DECAY` の倍率で減衰します。候補選択では、CPU 側の記録のうち最も heat が高い expert と、VRAM 側で最も heat が低い expert を比較します。条件は次の通りです。

```text
CPU 側の最大 heat > VRAM 側の最小 heat * DS4_CACHE_MARGIN + DS4_CACHE_BONUS
```

条件を満たすと swap を queue に追加し、cache worker が処理します。したがって margin は単独で swap を有効化する switch ではなく、expert cache と上記の候補・空き slot・inflight 条件がそろった際の閾値です。`DS4_CACHE_MARGIN` 自体について専用の警告・ログ・失敗経路は見つかりませんでした。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:116-120`。
- 既定値、環境読み取り helper、関連する `DS4_CACHE_BONUS` / `DS4_CACHE_DECAY` / `DS4_CACHE_INFLIGHT`: `src/dsv41/ds4_model.cu:1162-1168`。
- heat 減衰と swap 閾値の判定: `src/dsv41/ds4_model.cu:7329-7355`。
- cache tick 呼び出し: `src/dsv41/ds4_model.cu:9523-9531,9749-9754`。
- expert cache 無効時の worker 作成と上限適用: `src/dsv41/ds4_model.cu:3158-3172,7250-7252`。
- 全 expert が VRAM に収まる場合に swap 準備を行わない分岐: `src/dsv41/ds4_model.cu:4697`。
- `--no-expert-cache` CLI: `src/dsv41/ds4_main.cpp:104,1331`。CLI の既定値 `expert_cache=true`: `src/dsv41/ds4_model.hpp:37`。
- 独立実行ファイルと既定 OFF のビルド条件: `CMakeLists.txt:906-920`。
