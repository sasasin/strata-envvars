# `--session-min-free-mib`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata`（root の引数 parser） |
| オプション | `--session-min-free-mib N` |
| 別名 | なし |
| 値 | 0 以上の10進整数。MiB 単位。parser が受け付ける上限は `INT64_MAX / (1024 * 1024)`。 |

## 役割

`--serve` 実行中に session をファイルへ保存する `SAVE <path>` の前に、保存後も出力先ファイルシステムに残す空き容量を指定します。既定値は 4096 MiB です。`0` なら空き容量の事前確認を行いません。オプションの説明と既定値は `src/program/generate.cpp:744-745,905` にあります。

## 使い方

他の必須 serve 引数と一緒にエンジン起動時に指定します。例:

```sh
strata --serve --model /path/to/model.gguf --spec 2 --prefill 2048 --expert-cache auto --session-min-free-mib 8192
```

serve 中に session を保存するときは、エンジンの入力プロトコルで `SAVE /path/to/session.bin` を送ります。`SAVE` / `RESTORE` の行プロトコルと `SAVE` の成功応答 `SAVED ...` は `src/program/generate.cpp:12054-12063,12201-12204` に記載されています。実際の起動方法やモデル固有の必須引数は環境に合わせてください。

## 値と既定値

- 値は `std::from_chars` で整数として読み、文字列全体が数値として消費されること、範囲内であること、負数でないことを検証します。上限は MiB をバイトへ変換する左シフトでオーバーフローしない範囲です。無効値には標準エラーへ `--session-min-free-mib needs a nonnegative integer within range` を出し、終了コード 2 で終了します（`src/program/generate.cpp:2641-2653`）。
- 値を省略すると、次の引数が値として扱われます。次の引数自体がない場合は `--session-min-free-mib needs a value` を標準エラーへ出して終了コード 2 です（`src/program/generate.cpp:2418-2420,2644-2647`）。
- 指定しない場合は 4096 MiB です（`src/program/generate.cpp:744-745`）。同じフラグを複数回指定すると parser のループで後の値が同じ設定値を更新します（`src/program/generate.cpp:2416-2420,2644-2659`）。

## 実行時の動作

`SAVE` 処理では、session の内容からヘッダー等を含む新しいファイル全体の必要サイズを算出し、`--session-min-free-mib` をバイトへ変換して書き込み API に渡します（`src/program/generate.cpp:12185-12192`; `src/core/conversation_file.cpp:1035-1042`）。設定値が 0 より大きい場合、エンジンは出力先のあるファイルシステムの空き容量を調べ、`新しいファイル全体のサイズ + reserve` が空き容量以下でなければ SAVE を拒否します（`src/core/conversation_file.cpp:1043-1052`）。POSIX 系では `statvfs` の利用可能ブロック数から計算し、Windows では `GetDiskFreeSpaceExW` を使います（`src/core/conversation_file.cpp:326-332,520-524`）。

この確認は書き込み前の preflight で、容量の予約や上限設定ではありません。確認後に他のプロセスが容量を使えば、書き込みが失敗する可能性があります（`include/strata/core/conversation_file.hpp:143-147`）。既存ファイルを置き換える場合も、新しい session file の全サイズで preflight します。古いファイルのサイズを差し引く処理はありません（`src/core/conversation_file.cpp:1041-1055`）。`0` はこの空き容量チェックだけを無効にし、実際の書き込み時に起きる容量不足を防ぎません。

## 適用条件と副作用

- 通常エンジンの `--serve` で `SAVE` を処理するときにだけ使われ、`RESTORE` 時には参照されません。値を設定する箇所は `save` 分岐内です（`src/program/generate.cpp:12117-12118,12185-12192`）。
- `--serve` は別途 `--spec T` と `--prefill CHUNK` 等の条件を要求します（`src/program/generate.cpp:8354-8359`）。session file の SAVE / RESTORE 自体も layer split、peer device、batch、`--prompt-cache <= 0` との併用を拒否します（`src/program/generate.cpp:12094-12099`）。
- この値は RAM の余裕を判定する `--conversation-cache-min-free-mib` とは別です。SAVE の RAM preflight はそちらの設定値を使用し、ディスクの reserve は本オプションで判定します（`src/program/generate.cpp:12143-12164,12185-12190`）。
- 通常の C++ エンジン parser のほか、SYCL 実装にも同じ名前、既定値、整数範囲検証、SAVE 時の受け渡しがあります（`sycl/src/program/generate.cpp:686-687,826,1937-1950,9551-9558`）。
- 索引では Qwen3.6 専用 parser は別の `strata-engine/qwen36/` scope とされています（`docs/cli/README.md`）。この文書の対象は索引どおり通常エンジン root parser です。

## 出力とエラー

- 空き容量が reserve を満たさないと、session writer は `SessionError::storage` と「not enough disk space ...」の理由を返し、エンジンは標準エラーに `strata serve: session save <path>: ...`、標準出力に `SERR storage 0 <reason>` を出します。この preflight は一時ファイル作成前に行われるため、この拒否経路では出力先を変更しません（`src/core/conversation_file.cpp:1043-1052`; `src/program/generate.cpp:12069-12077,12185-12192`）。
- 空き容量を取得できない場合は「cannot read the free disk space ...」で失敗し、writer の初期エラー種別 `io` のまま `SERR io 0 ...` となります（`src/core/conversation_file.cpp:1042-1045`; `src/program/generate.cpp:12069-12077,12185-12192`）。
- 保存が成功すると標準エラーに保存先などの要約、標準出力に `SAVED <tokens> <bytes> <ms>` を出します（`src/program/generate.cpp:12201-12204`）。確認後の書き込み・flush・rename などで起きる失敗はこの容量チェックとは別の失敗経路です。

## 根拠

- parser、既定値、ヘルプ、整数範囲検証: `src/program/generate.cpp:744-745,895-906,2416-2420,2641-2661`
- SYCL parser と SAVE への接続: `sycl/src/program/generate.cpp:686-687,820-826,1937-1950,9551-9558`
- SAVE 時のディスク容量値の受け渡し、SAVE の拒否条件と応答: `src/program/generate.cpp:12054-12077,12094-12099,12117-12118,12185-12204`
- 空き容量 preflight、サイズ比較、プラットフォーム別取得: `src/core/conversation_file.cpp:326-332,520-524,1035-1055`
- preflight が予約ではないこと: `include/strata/core/conversation_file.hpp:143-147`
- コマンド階層と option scope: `docs/cli/README.md:1128-1134,1277-1280,1318-1322`

同一 revision の既存 CLI `--help` バイナリは使用していません。ヘルプ文言は checkout 内の parser ソースで確認しました。ディスク空き容量の取得・保存動作は実行せず、ソース読解に基づく調査です。
