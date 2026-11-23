# `strata-hy4-metal --no-flash`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--no-flash` |
| 別名 | なし。`--flash` は同じ設定を反対に戻す独立オプション |
| 値 | 値を取らないフラグ |

## 役割

通常の非 speculative prefill attention で、16 token 以上の chunk に使う K-streamed Flash-MLA の選択を無効にします。Flash-MLA と通常 attention の経路を比較・切り分けたい場合に使えます。Metal の `--serve` 経路ではこの設定は Runner に渡されず、既定値のままです。

## 使い方

```sh
strata-hy4-metal --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --no-flash
```

モデル、Engram、token ID ファイルを指定した通常の実行で、prefill の Flash-MLA 選択を止めます。

## 値と既定値

- 値を取りません。parser は引数を消費せず `no_flash = true` にします。数値などを後ろに付けても値として検証されず、次の引数として処理されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1532-1534`）。
- 既定は無効です。`no_flash` の初期値は `false` で、Runner の `flash_on` 初期値は `true` です（同 `:1490`, `:334`）。
- 同じ実行で `--flash` を指定すると `no_flash = false` に戻ります。複数回指定した場合は parser が左から処理するため、最後に現れた `--flash` または `--no-flash` が設定を決めます（同 `:1532-1534`）。
- 範囲検証や `--no-flash` 固有のエラー処理はありません。

## 実行時の動作

通常実行では `no_flash` の反転値を `Runner::flash_on` に設定し、その Runner が prefill chunk を処理します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1715-1721,1740`; 同 `:1790-1795`）。通常 attention 分岐では、tree 処理に該当しない場合、`flash_on` が真で、Metal 4 Flash kernel が利用可能なら MPP Flash kernel、そうでなくても `T >= 16` かつ head 数が 16 の倍数なら simdgroup Flash kernel を選びます。`--no-flash` はこの二つの条件を偽にし、該当 chunk を `mla_attend` の通常経路へ進ませます（同 `:1067-1086`）。

このフラグは `--no-mpp-flash` と別の設定です。`--no-mpp-flash` は MPP Flash の利用可否を制御し、`--no-flash` は上記の prefill Flash attention 分岐自体を止めます。`--no-flash` だけでは、tree attention や `T <= 8` の split attention の分岐（同 `:1052-1066,1071-1086`）、また `mpp_flash_on` を参照する Q/K 準備・V 投影（同 `:1016-1024,1092-1101`）は無効化しません。

## 適用条件と副作用

- 効果があるのは通常実行の該当 attention 分岐です。chunk が 16 token 未満、head 数が 16 の倍数でない場合、または tree 経路ではもともとこの `flash_on` 条件で Flash kernel を選ばないため、このフラグによる分岐差はありません（同 `:1052-1070`）。
- `--serve` を指定すると、`main` は `ServeOpts` を作って `hy4_serve_main` へ戻ります。その `ServeOpts` に flash 設定のフィールドはなく、serve 側は新しい Runner を既定値で作成します。そのため `--no-flash` は serve 中の Runner に適用されません（同 `:1636-1674`; `engine/src/hy4flash/metal/hy4_metal_serve.h:24-38,219-225`）。
- ファイルや設定を変更する副作用はこのフラグ自体にはありません。選択する GPU kernel の経路を変更します。性能・メモリ量への定量的な影響はソースからは確定できません。

## 出力とエラー

フラグ自体に専用の出力や validation error はありません。`--no-flash` の後に未知の引数があれば、一般の未知オプション経路で stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して終了コード 2 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490,1504-1506,1532-1534` — 初期値、引数 parser、`--flash` との上書き関係。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:330-334,1067-1086,1740-1741` — Runner の既定値、Flash-MLA 選択条件、通常 attention へのフォールバック。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674,1715-1721,1790-1795` — serve への早期委譲と通常実行での Runner 設定・利用。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:24-38,219-225` — serve 設定に flash フラグがなく、Runner が既定値で作られること。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609` — 未知引数時の出力と終了コード。
