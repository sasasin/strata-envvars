# `DS4_CHECK_BUF`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`DS4_CHECK_BUF` は、DeepSeek 用 Metal runtime が compute dispatch のバッファ引数を encoder に設定する際、解決後のバッファ offset が `MTLBuffer` の長さ以上なら stderr に診断行を出す開発・診断用フックです。値を変換して計算設定に使うものではなく、バッファ引数の範囲を検査するログ制御です。

この読み取りは `STRATA_DS4_RUNTIME` のコンパイル分岐内にあります。Metal build は macOS 専用で、`metal/CMakeLists.txt` は `mtl_rt.mm` を `STRATA_DS4_RUNTIME=1` でコンパイルし、DeepSeek 専用の `strata_ds4` target にリンクします。同ファイルのコメントによれば、通常の Qwen engine (`strata`) ではこの macro は無効です（`metal/CMakeLists.txt:1-2,151-165`）。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効。診断行を出さない |
| 空文字を含む、何らかの値が設定済み | 有効。値の内容は読まず、設定の有無だけを見る |

`std::getenv("DS4_CHECK_BUF") != nullptr` で判定し、結果は関数内の `static const bool` に保存されます。文字列比較、数値変換、大小文字の判定、範囲制限はありません。未設定への変更を含め、初回判定後の環境変更は再評価されません（`metal/src/mtl_rt.mm:719-728`）。

## 有効になる条件

- macOS の Metal build で、`STRATA_DS4_RUNTIME` を有効にしてビルドされた `strata_ds4` の runtime 経路を通ること（`metal/CMakeLists.txt:1-2,151-165`）。
- `encode()` が `Dispatch` 内のバッファ引数を処理すること。inline bytes 引数（`Arg::buf == nullptr`）にはこの検査を行いません（`metal/src/mtl_rt.h:46-53`, `metal/src/mtl_rt.mm:719-731`）。
- その `encode()` 呼び出し時点で、最初に評価された `DS4_CHECK_BUF` の値が設定済みであること。CLI 引数、設定ファイル、別の環境変数でこの判定を上書きする処理は、候補名の全参照検索では見つかりません。

`Context::run()` からは単一 dispatch の deferred 経路と通常の dispatch ループの両方で `encode()` が呼ばれます（`metal/src/mtl_rt.mm:902-928,958-966`）。

## 実行時の詳細

各バッファ引数について `BO(*a.buf, a.off, o)` で Metal buffer と offset `o` を得た後、設定が有効で `o >= [mb length]` なら、stderr に次の形式で出力します。

```text
mtl: <kernel> arg <index>: offset <offset> past the buffer (<length> bytes; Buffer.bytes <bytes> bias <bias> off <argument offset>)
```

比較対象は offset と buffer 長だけです。等しい場合も診断対象です。診断後も ` [enc setBuffer:mb offset:o atIndex:i]` を呼び出します。この箇所自体は offset を clamp せず、dispatch を中止せず、エラー終了もしません。後続の Metal API や GPU がどう扱うかはこの Strata コードからは断定しません（`metal/src/mtl_rt.mm:719-731`）。

ログは各該当バッファ引数の encode 時に出るため、dispatch ごとに出力され得ます。読み取り結果の static cache は `encode()` 内のバッファ引数分岐にあり、プロセス起動直後ではなく、最初にその分岐へ到達した時に初期化されます（`metal/src/mtl_rt.mm:719-728`）。

## 根拠

- 環境変数の全参照と診断条件・出力: `metal/src/mtl_rt.mm:719-728`。リポジトリ全体の完全一致検索で、候補名のソース参照はこの1箇所でした。
- バッファ引数と inline bytes 引数の区別: `metal/src/mtl_rt.h:46-53`。
- `encode()` の呼び出し経路: `metal/src/mtl_rt.mm:902-928,958-966`。
- macOS 専用 build と DS4 runtime macro / target: `metal/CMakeLists.txt:1-2,151-165`。
- `docs/DETAILS.md` に `DS4_CHECK_BUF` の挙動を説明する記述は確認できませんでした。
