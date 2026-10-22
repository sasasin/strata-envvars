# `STRATA_RAM_ADAPT_SKIP_TOP`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

resident RAM の適応選択（`STRATA_RAM_ADAPT2` と `STRATA_RAM_ADAPT` を組み合わせる経路）で、各 layer の RAM 昇格候補から、GPU 適応層が次の選択で取りそうな上位候補を除外します。これにより、RAM の枠を GPU 側にも選ばれそうな expert に使うことを避けます。この変数は RAM 適応選択の候補を絞るもので、GPU の選択規則そのものを変更しません。

## 値と判定

`--serve` の初期化時に `std::atoi` で整数へ変換し、0 以上に clamp します。環境変数が未設定なら既定値は `2` です。

| 入力 | `skip_top` の値 |
|---|---:|
| 未設定 | 2 |
| `0`、負の整数 | 0 |
| 正の整数 | その整数 |
| 空文字、整数として先頭を読めない文字列 | 0（`atoi` が 0 を返す） |
| 整数の後ろに文字が続く値（例: `3x`） | 先頭から変換できた整数（例: 3） |

`atoi` のため、文字列全体の妥当性や後続文字は検査しません。空白や符号などの解釈も `atoi` に従います。設定値を読み直すループはなく、初期化後にプロセス環境を変えても値は更新されません。

## 有効になる条件

値が読み込まれても、次の条件を満たす RAM 適応選択の分岐でのみ使われます。

- `STRATA_RAM_ADAPT` が正数である（未設定時は 0）。
- `STRATA_RAM_ADAPT2` が設定され、`atoi` の結果が 0 以外である。
- 最初の decode window の後で、適応使用量 `drive.d.usage` が空でない。
- 先行する適応 swap が pending でなく、非同期 adaptive job がある場合は idle である。
- resident RAM の補完コピーが利用可能（`src.complement_ready()`）、単一 GPU、peer GPU なし、remote expert 最適化なし、`--batch 0` である。

これらの条件を満たさない場合、この値による候補除外は実行されません。関連する RAM 適応選択自体が `--serve` の window loop 内にあります。

## 実行時の詳細

各 layer で、まず VRAM にない expert を調べます。resident RAM にあるものは退避候補 `outs` に、RAM にないもののうち `usage + prompt seed >= 2.0` のものは昇格候補 `ins` に入ります。`STRATA_RAM_ADAPT_SKIP_TOP > 0` かつ候補があるとき、`ins` 内の expert の **decode usage `u[e]` のみ**を降順に並べた第 `k` 位（`k = min(skip_top, 候補数)`）の値を境界とし、`u[e]` が境界以上の候補を最大 `k` 個 `ins` から除外します。ここでは prompt seed を足した値ではなく decode usage を使います。同値の境界候補が複数ある場合、除外対象の選ばれ方は `nth_element` の順序に依存します。

残った昇格候補と退避候補から、後続処理がスコア順に RAM 交換を選びます。したがって、この値は RAM に入れる候補だけを除外し、GPU tier が実際にその expert を選ぶことや、RAM 交換の成立を保証しません。0 なら除外処理を飛ばし、候補数以上の値ならその layer の昇格候補をすべて除外します。

この環境変数専用のログはありません。`STRATA_RAM_ADAPT2` が有効な serve の終了時には、staged reads、installed 数、install 時に skipped となった数をまとめて stderr に出しますが、`STRATA_RAM_ADAPT_SKIP_TOP` が何候補を除外したかは出力しません。

## 根拠

- `src/program/generate.cpp:8267-8283` — serve 初期化時の `RamAdapt2` 既定値と環境変数の読み取り・clamp。
- `src/program/generate.cpp:14794-14807` — `STRATA_RAM_ADAPT` との組み合わせ、window 条件、適用範囲。
- `src/program/generate.cpp:14820-14849` — layer ごとの候補作成、usage 上位候補の除外、以降の候補数制限。
- `src/program/generate.cpp:14850-14875` — 残った候補のスコアリングと RAM stage 数の上限。
- `src/program/generate.cpp:15368-15372` — `STRATA_RAM_ADAPT2` の累積処理数ログ。
- `docs/DETAILS.md:172-181` — `STRATA_RAM_ADAPT` の基本動作と適用条件。ここでは `STRATA_RAM_ADAPT_SKIP_TOP` の既定値や上位候補除外の詳細は説明されていません。
