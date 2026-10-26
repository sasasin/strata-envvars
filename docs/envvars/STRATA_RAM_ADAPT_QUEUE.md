# `STRATA_RAM_ADAPT_QUEUE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

resident RAM 適応の staged promotion が保持できる未回収ジョブ数を制限します。ジョブは、対象 expert blob のファイル読み込みと、その後の RAM resident slot への install を待つ単位です。上限に達すると `ram_stage()` は新しいジョブを追加せず `false` を返します。これは1 window あたりに候補とする件数（`STRATA_RAM_ADAPT`）とは別の、`FileExpertSource` のキュー容量です。

## 値と判定

`FileExpertSource::ram_stage()` 内の関数ローカル `static const size_t` として、最初に staging を試みたときに一度だけ読み取ります。値は `std::atoi()` で整数に変換し、`std::max(1, ...)` で最低値を1にします。未設定時だけ64です。

| 環境変数の状態 | キュー上限 |
|---|---:|
| 未設定 | 64 |
| `"8"` | 8 |
| `"8tail"` | 8（`atoi` が先頭の整数部分を変換） |
| 空文字、数字で始まらない文字列、`"0"`、負数 | 1 |

空白や符号を含む文字列も `atoi` の規則で変換されます。文字列全体の妥当性検査や明示的な上限 clamp はありません。`atoi` の変換範囲を超えた入力の結果はこの実装で別途処理されません。

## 有効になる条件

この変数だけで RAM 適応を有効化することはありません。読み取りと上限の適用が起きるのは、`ram_stage()` が呼ばれた場合だけです。呼び出し側では少なくとも次の条件が必要です。

- `STRATA_RAM_ADAPT` が正の数として解釈される。
- `STRATA_RAM_ADAPT2` が設定され、`atoi` の結果が0以外。
- 初回 window ではなく、usage データがあり、保留中の適応 swap がない。
- 非同期適応ジョブがないか idle である。
- resident RAM copy が利用可能で、単一 GPU、peer device なし、remote expert optimization なし、`--batch` なし。

呼び出し側は window ごとに `STRATA_RAM_ADAPT` の値を上限として staging 数を止めます。一方、`STRATA_RAM_ADAPT_QUEUE` はジョブ総数（読み込み待ち、読み込み中、完了後に install 回収されていないものを含む）が上限以上なら拒否します。既存ジョブと同じ layer で expert の組が重なる場合も登録しません。したがって、上限に空きがあっても重複や resident 状態等の条件で staging に失敗することがあります。

## 実行時の詳細

`ram_stage()` は有効な候補をキューに追加し、必要なら `strata-ram` worker thread を起動します。worker は一度に1 jobずつ `copy_from_files()` で blob を読み、成功・失敗を job state に記録します。decode 側の window 境界で呼ばれる `ram_install()` は完了済みジョブをキューから回収し、読み込み成功かつ対象 expert が GPU tier に取られていない場合に RAM resident slot へ install します。完了した job もこの回収まで `ram_jobs_` に残るため、その間は queue cap を消費します。

環境変数の上限自体を示す専用ログはありません。`STRATA_RAM_ADAPT2` が有効な場合、終了時の累積ログ `resident RAM (STRATA_RAM_ADAPT2): ... promotions read on the I/O thread, ... installed, ... skipped at the install ...` に読み込み・install・skip 件数が出ます。queue cap による拒否数は個別には出力されません。

## 根拠

- `src/core/expert_source.cpp:4370-4392` — 適用時期、既定値64、`atoi` と最低値1、上限判定、重複判定、worker 起動。
- `src/core/expert_source.cpp:4402-4454` — worker のファイル読み込みと、window 境界での完了 job 回収・install。
- `src/program/generate.cpp:8411-8427` — `STRATA_RAM_ADAPT2` と関連重み等の初期値・読み取り。
- `src/program/generate.cpp:14992-15014,15045-15075` — `STRATA_RAM_ADAPT` の既定値・解釈、適用条件、window ごとの候補数と staging 呼び出し。
- `src/program/generate.cpp:15592-15596` — staged promotion の累積ログ。
- `docs/DETAILS.md:241-242` — `STRATA_RAM_ADAPT` の利用説明。`STRATA_RAM_ADAPT_QUEUE` 自体の説明や容量値は見つからず、上記の挙動は対象 commit の実装から確認。
