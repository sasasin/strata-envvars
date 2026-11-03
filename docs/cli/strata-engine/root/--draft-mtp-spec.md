# `strata generate --draft-mtp-spec`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--draft-mtp-spec N` |
| 別名 | なし |
| 値 | 整数。パーサーで最低値を 2 に補正し、上限はこのオプション単独では設けない |

## 役割

`--draft auto` で MTP drafter を選んだリクエストの最大検証 window 幅を指定します。既定値は 4 です。通常の `--draft mtp` では使われません。明示的に指定した場合は、`--draft dflash2` の起動に失敗して MTP に切り替わる際にも、その MTP 用 window 幅として使われます（`src/program/generate.cpp:998-1000,6817-6818`）。

## 使い方

```sh
strata generate --pack ./target-pack --tokens "1,2,3" --serve \
  --mtp ./mtp --spec 8 --draft auto --draft-model ./dflash2-pack \
  --draft-mtp-spec 4
```

これは `--draft auto` の MTP リクエストに対して幅 4 を指定する例です。`--draft auto` は serve 用の選択方式で、両 drafter を用意し、リクエスト単位で選びます（`src/program/generate.cpp:1163-1164`）。

## 値と既定値

- 省略時の内部既定値は `4` です（`src/program/generate.cpp:998`）。
- 指定値は `std::atoi` で整数化した後、`std::max(2, value)` により 2 未満を 2 に補正します。専用の範囲エラーや正の数の validation はありません（`src/program/generate.cpp:3580`）。たとえば `0` や負数は 2 になります。数値として解釈できない文字列も `atoi` の結果を下限処理するため、明示的な不正値エラーにはなりません。
- 上限は指定値そのものにはありませんが、実行時の MTP 幅は全体の `--spec` と `--mtp-max-t`（正の値がある場合）で制限されます（`src/program/generate.cpp:13389-13397`）。
- 値を省略すると `--draft-mtp-spec needs a value` を stderr に出して終了コード 2 で終了します。オプションを複数回指定した場合、parser が同じフィールドを逐次代入するため最後の値が残ります（`src/program/generate.cpp:3293-3298,3580`）。

## 実行時の動作

`--draft auto` の serve ループでは、MTP 用の幅を `min(S_mtp_wide, max(2, draft_mtp_spec))` として算出します。ここで `S_mtp_wide` は `--spec` と正の `--mtp-max-t` の小さい方（`--mtp-max-t` が指定されない場合は `--spec`）です。選ばれた request が MTP を使う場合にこの幅を適用し、DFlash2 を使う request は広い側の `S_mtp_wide` を使います（`src/program/generate.cpp:13389-13397,15211-15234`）。

リクエスト側に `draft=mtp|dflash2` があればそれが drafter 選択に使われ、なければ `--draft-rule` が選択します。`--draft-rule learn` の選択機構を含め、このオプション自体は選択方式を変えず、MTP が選択された場合の幅だけを制限します（`src/program/generate.cpp:997,15213-15234`）。

`--draft dflash2` で `--draft-mtp-spec` を明示していて、DFlash2 の利用条件を満たさない、または起動・bind・prepare に失敗して MTP fallback が使われる場合、エンジンは `--spec` が指定値より大きければ `o.spec` をこの値まで下げます。指定がない場合はこの fallback 用の縮小を行いません（`src/program/generate.cpp:6765-6818,11160-11169,19698-19718`）。一方、`--draft-fallback none` では MTP をロードしないため、DFlash2 が起動できないと起動・実行を終了します（`src/program/generate.cpp:6811-6814,19720-19722`）。

## 適用条件と副作用

- 主な適用先は `--draft auto` の serve リクエストで、MTP が選ばれたときの提案・検証 window を狭めます。MTP drafter は当該幅に合わせて最大 draft 数も更新されます（`src/program/generate.cpp:13391-13397,15230-15234`）。
- `--draft auto` は両 drafter を維持しリクエストごとに選択するモードです。実際に DFlash2 が使えるかは build と起動条件に依存し、利用できない場合は各リクエストが MTP を使います（`src/program/generate.cpp:995-1000,6765-6774,15211-15216`）。
- 明示した値は DFlash2 起動失敗時の MTP fallback の `--spec` も縮小し得ます。この変更はエンジン内部の window 設定であり、本オプション自体がファイル、ネットワーク、別プロセスを操作する処理は確認できません。
- `--draft mtp` の単独利用では、本値を参照する分岐はありません。通常の MTP window は `--spec`、`--mtp-max-t` など別の設定で決まります（`src/program/generate.cpp:13389-13397`）。

## 出力とエラー

値がない場合の stderr と終了コード 2 は上記の通りです。値の範囲外や数値変換失敗について、このオプション専用の警告・エラー出力はありません（`src/program/generate.cpp:3295-3297,3580`）。DFlash2 起動失敗時の診断・終了は fallback 設定や失敗箇所に依存し、本オプションが直接出力するメッセージではありません（`src/program/generate.cpp:6802-6818,11160-11168,19704-19722`）。

## 根拠

- `src/program/generate.cpp:998-1000` — 既定値、明示指定フラグ、および MTP 用途。
- `src/program/generate.cpp:3293-3298,3580` — parser、値省略時の失敗、整数変換と下限補正。
- `src/program/generate.cpp:1163-1164` — help に記載された `--draft auto` と本オプションの関係。
- `src/program/generate.cpp:13389-13397,15211-15234` — serve request ごとの drafter 選択と MTP window 適用。
- `src/program/generate.cpp:6765-6818,11160-11169,19698-19722` — DFlash2 の適用条件、fallback、失敗時の経路。

調査範囲は上記 commit の Strata ソースです。CLI バイナリや各 backend の実機実行は行っていないため、backend ごとの配布・実行結果は確認していません。
