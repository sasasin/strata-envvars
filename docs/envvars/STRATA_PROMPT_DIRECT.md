# `STRATA_PROMPT_DIRECT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Linux の `--mmap-experts` と RAM 予算付き実行で、ファイル層を buffered に保つ場合に、prompt の expert 一括読み取りだけを `O_DIRECT` に切り替えます。GPU キャッシュに入っている expert や RAM コピーにある expert は従来どおりそこからコピーします。decode の単体読み取り経路は切り替えません。

## 値と判定

値全体の parse はせず、環境変数が設定されていて先頭文字が `'1'` かどうかを調べます。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定済みだが先頭文字は `\0`） |
| 先頭文字が `1`（`1`, `10`, `1abc` など） | 有効 |
| その他（`0`, `true`, ` 1` など） | 無効 |

この値は起動処理中の条件分岐で一度評価されます。後から環境を書き換えても再評価されません。

## 有効になる条件

実際に prompt の直接読み取りを開くには、次の条件が必要です。

- `--mmap-experts` を指定し、`--resident-budget-gib` 相当の RAM 予算が正である。
- 起動時の unbuffered 読み取り処理が残っていない（`startup_kept` が false）。
- 実 RAM コピー構築後の `recheck_unbuffered()` が buffered 読み取り（`ub == false`）を選ぶ。
- 変数の先頭文字が `1` である。
- Linux 上で expert ファイルを開けること。

したがって、RAM 予算がない場合、ファイル層自体が既に unbuffered の場合、または変数が無効な場合には、この変数による切り替えはありません。Windows でも条件分岐は通りますが、`open_prompt_direct()` は Linux 専用として失敗を返し、prompt 読み取りは buffered のままです。

## 実行時の詳細

`generate.cpp` の起動処理が条件を満たすと `FileExpertSource::open_prompt_direct()` を呼び、Linux では各 expert ファイルを `O_RDONLY | O_DIRECT | O_CLOEXEC` で開きます。成功すると stderr に `strata generate: the prompt path's expert reads go unbuffered (STRATA_PROMPT_DIRECT=1)` と出ます。開けない場合は `stay buffered: ...` と理由を出します。部分的に開いた descriptor は閉じられます。

prompt の `Prefill` stager は expert を複数まとめて `copy_blobs()` に渡します。`pdirect_` が開いていると、RAM コピーにない blob を `read_direct()` で読みます。Linux では 4 KiB 境界に合わせた範囲を作り、近接する範囲を最大 32 MiB までまとめて非同期 I/O に投入します。読み取りに失敗した場合は各 blob を通常のファイルマッピング経由でコピーし直します。`copy_blob()` を使う decode 経路は `pdirect_` を参照しないため、ファイル層の通常の buffered 動作を保ちます。

測定結果はコードの動作保証ではありません。`docs/QUANTS.md` は、記載された RTX A4000 / UD-Q4_K_XL の測定では固定 flags の6 promptすべてで出力が一致し、4K prompt が 152→315 tokens/s、20K prompt が 217→500 tokens/s、decode が +2〜15% だったと記載しています。一方、別 PC では prompt や後続 decode の速度が低下した例も記載されており、この機能は opt-in のままです。

## 根拠

- 環境変数の読み取り、適用条件、結果ログ: `src/program/generate.cpp:7167-7184`。
- `O_DIRECT` descriptor のオープン、Linux 専用条件、失敗時の理由: `src/core/expert_source.cpp:1649-1669`。
- prompt stager からの一括コピー呼び出し: `src/prefill/prefill.cpp:524-538`。
- `copy_blobs()` が RAM コピーを優先し、残りを直接読み取り、失敗時にマッピングへ戻る処理: `src/core/expert_source.cpp:2534-2564`。
- Linux の直接読み取りで `pdirect_` を使う箇所: `src/core/expert_source.cpp:2005-2010,2081-2082`。
- 記載された測定条件と結果: `docs/QUANTS.md:134-143`。
