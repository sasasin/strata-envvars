# `STRATA_SSD_KEEPALIVE_WINDOW`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・ドライバーの環境変数は対象外。

## 役割

PLE（n-gram テーブル）を `--ple-io direct` で読むときの SSD keep-alive 読みを続ける時間窓を秒単位で指定します。窓の基準は最後に PLE 行を要求した時刻（`PleReader::issue()`）です。期限内に reader の I/O ワーカースレッドがアイドルになると、テーブル内のページを読む keep-alive が実行されます。期限を過ぎると keep-alive は止まり、次の行要求で再開します。

環境変数は `strata generate` が PLE テーブルを開くときに読み、`PleIoOptions` から `PleReader::set_keepalive()` へ渡します。ソースには同じ設定処理が CUDA/HIP 側と SYCL 側にあります。

## 値と判定

`std::getenv` で取得し、未設定または空文字なら `60.0` 秒です。それ以外は `std::atof` の結果を `std::clamp(..., 1.0, 86400.0)` に渡します。文字列全体の妥当性は検査しません。

| 入力 | `keepalive_window_s` |
|---|---:|
| 未設定、空文字 | 60 秒 |
| 数値（例 `30`, `2.5`, `1e2`） | 数値を秒として使用 |
| 数値の後ろに文字がある（例 `30sec`） | `atof` が読んだ先頭部分、つまり 30 秒 |
| 数値に変換できない文字列 | `atof` の 0 を下限 clamp し、1 秒 |
| 0 または負数 | 下限 clamp により 1 秒 |
| 1 未満 | 1 秒 |
| 86400 超 | 86400 秒（24 時間） |

空白は `atof` の数値変換規則に従います。大文字小文字や真偽文字列による判定はありません。例えば `false` は 1 秒、`60s` は 60 秒です。値は double で保持されます。

## 有効になる条件

- PLE テーブルが指定され、`o.ple_gguf` が空でない場合に限り読み取られます。
- 値が動作に使われるのは PLE の Direct I/O 経路です。`--ple-io mmap` / `--ple-io ram` では `STRATA_SSD_KEEPALIVE` 側の周期が 0 にされるため、この窓を設定しても keep-alive は発生しません。
- `--ple-sync-submit` で I/O ワーカーを使わない場合も周期が 0 になります。reader 側も keep-alive の周期を有効にする条件として threaded mode を要求します。
- Direct 読みの速度プローブが遅く、`--ple-io` が明示指定されていない場合、実装は mmap に切り替えて周期を 0 にします。この fallback 後は窓の設定は効きません。
- 周期を有効にする `STRATA_SSD_KEEPALIVE` が 0 なら窓だけを設定しても読みは走りません。
- PLE の行要求が少なくとも一度あり、最後の要求から設定窓以内で、reader がエラー状態でなく、ワーカーがアイドルである間に限り keep-alive が行われます。要求処理中（キューまたは in-flight job がある間）にはアイドル時の keep-alive 判定を行いません。

## 実行時の詳細

- `PleReader::set_keepalive()` は窓を秒からマイクロ秒へ換算し、reader の状態に保存します。`keepalive_due()` は `now - last_issue_us > keep_window_us` なら期限切れとして keep-alive を無効扱いにします。境界ちょうど（経過時間が窓と等しい間）は期限内です。
- keep-alive の周期そのものは別環境変数 `STRATA_SSD_KEEPALIVE` で決まります。worker は idle wait 中に周期到来を判定し、期限内なら PLE テーブル内の 1 ページを読みます。
- 窓を過ぎると読みを止めます。後の `issue()` が窓外であれば、行がすべてキャッシュヒットで新しい I/O job がなくても worker を起こし、keep-alive を再開します。
- 環境変数の取得・変換は PLE 構築時に一度だけです。生成中にプロセス環境を書き換えても再読込されません。設定値そのものは `static` キャッシュではなく、その reader インスタンスの状態に保存されます。
- keep-alive の起動ログは周期が正の場合に出ます。`keepalive_window_s` は `%.0f` 表示のため、たとえば小数秒を指定してもログでは整数秒に丸めて表示されます。mmap 経路では keep-alive のログ行は出ません。

## 文書と資料の照合

`docs/DETAILS.md` にはこの変数の記載は見つかりませんでした。既存資料 `STRATA_SSD_KEEPALIVE.md` の「関連するもう一方の値」の記述は、読み取り箇所と clamp の実装に一致します。実装コメントは既定 60 秒と説明していますが、具体的な窓の効果や測定値を示す資料は確認できませんでした。

## 根拠

- CUDA/HIP 側での読み取り、既定値、変換、clamp、適用条件: `src/program/generate.cpp:3149-3167`
- 起動時の keep-alive ログ: `src/program/generate.cpp:3216-3221`
- mmap への fallback と周期の無効化: `src/program/generate.cpp:3174-3199`
- SYCL 側の同じ値判定と条件: `sycl/src/program/generate.cpp:2975-2994`
- Direct mode のみ `set_keepalive()` を呼ぶ箇所: `src/kernels/ngram.cpp:314-328`
- 窓の秒からマイクロ秒への変換: `src/ngram/ple_reader.cpp:517-525`
- 期限判定、ページ読み、idle worker の処理: `src/ngram/ple_reader.cpp:180-198,299-325`
- 次の `issue()` による再開: `src/ngram/ple_reader.cpp:422-430,471-478`
- options の既定値と適用範囲の説明: `include/strata/kernels/ngram.hpp:149-164`
