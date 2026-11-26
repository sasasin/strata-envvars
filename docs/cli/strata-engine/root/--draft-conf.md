# `--draft-conf`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--draft-conf P` |
| 別名 | なし |
| 値 | 数値。parser は `atof` で読み、`0.0`〜`1.0` に clamp する |

## 役割

`--draft dflash2` で DFlash2 が提案した候補を検証する窓幅を、候補ごとの selector 確率の累積積で制限します。累積積が `P` 未満になる候補の手前で窓を止めます。`P=0` は通常の窓幅選択に委ねます。

## 使い方

```sh
# DFlash2 の検証窓で、累積確率が 0.4 を下回る位置で窓を止める
strata --pack target.gguf --mtp draft-dir --draft dflash2 \
  --draft-model draft.pack --spec 8 --draft-conf 0.4
```

## 値と既定値

- 値は省略できません。値がない場合は `--draft-conf needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3846`）。
- `atof` の結果を `[0.0, 1.0]` に clamp します。したがって範囲外の負数は `0`、`1` より大きい数は `1` になり、数値として読めない文字列は `atof` の結果 `0` として扱われます（`engine/src/program/generate.cpp:4162`、`engine/sycl/src/program/generate.cpp:2126`）。
- 同じ指定を複数回書くと、引数を順に走査して同じフィールドへ代入するため最後の値が残ります（`engine/src/program/generate.cpp:3842-3847,4162`）。
- CUDA/HIP など `engine/src/program/generate.cpp` の parser では既定値 `0.0` です。SYCL parser では既定値 `0.6` です（`engine/src/program/generate.cpp:1191`、`engine/sycl/src/program/generate.cpp:789`）。

## 実行時の動作

window rule は DFlash2 がそのラウンドの候補元であり、`P > 0` で、確率配列がある場合にこの設定を適用します。窓幅 `T` を 1 から始め、候補確率 `dprob[0]`、`dprob[1]`…を順に掛け、累積積が `P` 以上の間だけ `T` を広げます。上限はその drafter の `cap` です（`engine/include/strata/spec/window_rule.hpp:16-27,57-70`）。実行ループは parser の値と DFlash2 の確率列をこの共通 rule に渡します（`engine/src/program/generate.cpp:25032-25038`、`engine/sycl/src/program/generate.cpp:14052-14058`）。

この条件は `--draft mtp` の候補には適用されません。`P > 0` の DFlash2 では `--spec-min-p` による個別確率の窓幅決定後に累積積ルールが窓幅を再設定するため、DFlash2 の窓幅は `--draft-conf` 側で決まります。`P=0` ならこの累積積ルールは無効で、通常の窓幅規則（`--spec-min-p` を含む）が使われます（`engine/include/strata/spec/window_rule.hpp:57-70`）。

CUDA/HIP 系の batch serve では別の窓制御もあります。`STRATA_BATCH_DF2_CONF` が空でない場合はその値が優先され、未設定または空の場合は `--draft-conf` が正ならその値、そうでなければ `0.35` が使われます。これは `--draft-conf 0` だけでは batch serve の累積積制御を無効にできないことを意味します。環境変数の値はここでは `atof` で読み、CLI parser のような clamp はしていません（`engine/src/program/generate.cpp:16802-16808,17140-17143`）。この batch serve 経路と共通 window rule は、同じ設定値を使いますが別の処理です。

## 適用条件と副作用

- DFlash2 が有効な build・実行経路でのみ意味があります。通常の engine parser では DFlash2 の選択と model pack が別途必要で、help は `--draft dflash2` を Flash-Next 向け CUDA/HIP の機能として説明しています（`engine/src/program/generate.cpp:1361-1366`）。SYCL の help も DFlash2 用として記載していますが、既定値は `0.6` です（`engine/sycl/src/program/generate.cpp:927-930`）。
- `P` は候補窓幅を変えます。CLI の通常生成では完了時、窓幅統計に `draft-conf` の値も表示します（`engine/src/program/generate.cpp:25264-25268`）。SYCL でも `P>0` なら窓幅統計行が出ますが、その行の表示項目は `min draft probability` と `--spec-min-p` の値であり、`--draft-conf` 自体は表示されません（`engine/sycl/src/program/generate.cpp:14246-14250`）。
- この値専用のファイル書き込みやネットワーク処理は確認できません。通常の DFlash2 推論が失敗した場合のエラー経路は `--draft-conf` 固有ではなく、drafter の呼び出し側が返すエラーを出力して終了します（例: `engine/src/program/generate.cpp:24961-24964`）。

## 出力とエラー

値の欠落は前述のとおり終了コード 2 です。値の数値形式や範囲について個別の拒否エラーはなく、parser で数値変換・clamp されます。生成が正常完了したときの窓幅統計は上記のとおりです（`engine/src/program/generate.cpp:3844-3846,4162,25264-25268`、`engine/sycl/src/program/generate.cpp:2126,14246-14250`）。

## 根拠

- `engine/src/program/generate.cpp:1191,1361-1366,4162` — CUDA/HIP 系の値の既定値、help、parser。
- `engine/sycl/src/program/generate.cpp:789,927-930,2126` — SYCL 系の既定値、help、parser。
- `engine/include/strata/spec/window_rule.hpp:16-27,57-70` — 適用条件、累積積による窓幅選択、`--spec-min-p` との順序。
- `engine/src/program/generate.cpp:25032-25038,25264-25268`、`engine/sycl/src/program/generate.cpp:14052-14058,14246-14250` — rule への値の受け渡しと完了時の統計出力。
- `engine/src/program/generate.cpp:16802-16808,17140-17143` — batch serve の `STRATA_BATCH_DF2_CONF` 優先順位と実際の累積確率判定。

値の浮動小数点境界（NaN 等）や、すべての build 構成での DFlash2 利用可否は、この調査では網羅的に確認していません。
