# `STRATA_TEST_UNMAP_GGUF`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Linux の GGUF expert file tier で、メモリマップを閉じた後の経路をテストするためのフックです。値を有効にすると、通常は Windows 側で行う GGUF shard の unmap を非 Windows 側でも試みます。コードコメントは Linux ではテスト専用と明記しています。この変数は `FileExpertSource::drop_mapping()` の一箇所でのみ読み取られ、サーバーや一般のモデル読み込み全体を有効化する設定ではありません。

## 値と判定

値は `std::atoi()` で整数変換され、変換結果が `0` なら無効、非 `0` なら有効です。文字列全体の検証はありません。したがって未設定、空文字、`0`、`0abc`、数値に変換できない文字列は無効です。`1`、`2`、`-1`、`1abc`、先頭の空白の後に非ゼロ数値がある文字列は有効になります。`atoi` の変換範囲外入力に対する結果はこの実装では別途検査されません。

根拠: `src/core/expert_source.cpp:1723-1725`。

## 有効になる条件

環境変数が非ゼロでも、以下をすべて満たす場合だけ非 Windows 側の unmap を試みます。

- `generate` が、メインの `FileExpertSource` (`srcp == &src`) を使っている。
- source が unbuffered I/O を選択している。
- `STRATA_KEEP_MAPPING` が未設定である。この別変数は値を検査せず、設定されていれば空文字を含めて `drop_mapping()` の呼び出し自体を止めます。
- `FileExpertSource` が GGUF の role mapping を持ち (`role_ptr_` が空でない)、unbuffered file handle (`direct_`) も持っている。

この環境変数を調べる実装は `#if defined(_WIN32)` の `#else` 側です。Windows ではこの名前を読まず、`drop_mapping()` が呼ばれれば Windows API で mapping を閉じます。`generate.cpp` は file tier の unbuffered 状態を確認してから関数を呼ぶため、mmap expert と resident budget を使わない経路などではこの変数は作用しません。

根拠: `src/program/generate.cpp:6874-6891`, `src/core/expert_source.cpp:1686-1726`。

## 実行時の詳細

`generate` は条件を満たした場合に `drop_mapping()` を呼び、stderr に `strata generate: the mapped view of the experts is closed (...)` または `... stays open (...)` を出します。非 Windows 側では、有効値、`role_ptr_`、`direct_`、未 unmap の条件を満たすと、各 shard の mapping を `munmap()` し、保持している file descriptor を閉じて `unmapped_` を立てます。成功時の括弧内理由には shard 数と `STRATA_TEST_UNMAP_GGUF` が含まれます。環境変数が無効、または role mapping がない場合は理由が `not Windows`、unbuffered handle がない場合は `the reads are not unbuffered` となり、上記のログは `stays open` になります。

unmap 後の GGUF expert 読み込みでは、`copy_from_files()` が先に unbuffered read を試します。そこが失敗した場合は mapping への fallback を試みますが、`unmapped_` のとき role mapping 経由の読み込みは失敗を返します。成功した unmap 後の expert 供給は unbuffered read に依存する構成です。`munmap()` が失敗した場合は `munmap failed` を返し、その時点で処理を中断します。

根拠: `src/program/generate.cpp:6885-6891`, `src/core/expert_source.cpp:1727-1736,1185-1225`。

## 資料との照合

`docs/DETAILS.md` および `docs/` 内に、この環境変数の記載は見つかりませんでした。現行動作と適用範囲は上記ソースコードに基づきます。コードコメント上の目的は Linux で Windows の unmap 経路をテストすることです。性能や正確性に関する測定値は確認できません。
