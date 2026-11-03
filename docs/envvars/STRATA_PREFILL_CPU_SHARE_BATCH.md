# `STRATA_PREFILL_CPU_SHARE_BATCH`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

serve の `--batch` 実行で、prompt の prefill に decode 用 CPU expert pool を渡せるようにする opt-in です。batch slot が decode 中の read では pool の share を止め、decode 中の slot がない read では利用を許可します。変数自体は share 量や CPU share の有効化を指定しません。実際に expert を CPU に割り当てるかは `STRATA_PREFILL_CPU_SHARE`、chunk、pool の有無などにも依存します。

## 値と判定

値全体を parse せず、`getenv()` が返す文字列の先頭文字だけを `'1'` と比較します（`src/program/generate.cpp:10123,16483-16484`）。

| 値 | 判定 |
| --- | --- |
| 未設定 | 無効 |
| 空文字 | 無効（値は設定済みでも先頭文字が `\0`） |
| `1`, `10`, `1abc` | 有効 |
| `0`, `true`, `false`, ` 1` など | 無効 |

無効値に対するエラーや警告、数値変換、範囲 clamp はありません。2か所の判定はそれぞれ関数内 static に保存され、各箇所の初回評価後に環境を書き換えても再評価されません。CLI 引数がこの値を上書きする処理はありません。

## 有効になる条件

- 対象は `strata serve` の経路です。serve 起動時に `--batch` が 1 以上で、この変数が有効、かつ `--no-pool` が指定されていない場合に `share_pool` が true になり、prompt 用 `Prefill` に CPU pool が設定されます（`src/program/generate.cpp:10124-10127,10629-10637`）。通常の batch なし serve では既に pool が対象で、この変数による追加効果はありません。
- 複数 GPU／layer split では未設定時の既定 share は arm されませんが、明示的な `STRATA_PREFILL_CPU_SHARE` は pool がある stage で有効になり得ます。serve は `by_default` を `stages.empty()` かつ `!multi_gpu` に限定して `arm_cpu_share` を呼びます。一方、`applies` は `share_pool` なので、明示値の share は複数 stage にも適用可能です。layer split では stage が pool を同時取得しないよう制御されます（`src/program/generate.cpp:10134-10135,10629-10637`; `src/prefill/prefill.cpp:2844-2872,3571-3581`）。
- prompt read ごとに batch slot の `active` 数を数え、1つ以上なら share を blocked にします。slot が decode 中でなければ解除します。各 run の前に更新されるため、slot の状態に応じて read の run ごとに判定し直します（`src/program/generate.cpp:16477-16487,16596-16605,16908-16915`）。独立した `STRATA_BATCH_CONCURRENT_READ` の経路では並行 decode 中の read を blocked にします（`src/program/generate.cpp:16613-16630`）。
- pool があっても、CPU share の実動作には別途 `STRATA_PREFILL_CPU_SHARE` が有効で、対象 chunk が `stream_all_min()` より小さく、pipe chunk ではなく、share が blocked でないことが必要です。`STRATA_PREFILL_CPU_SHARE` は未設定時の既定、完全一致の `auto`、または `atof` を clamp した 0〜1 の値で判定されます。pool の同時取得にも成功する必要があります（`src/prefill/prefill.cpp:257-260,262-290,3570-3581`）。このため、本変数だけを設定しても CPU share は有効になりません。
- CPU share は native expert layout など実装上の適格条件も確認します。native layout、非 null source、CPU share が停止されていないことなどを満たさなければ CPU 側へ expert を割り当てません（`src/prefill/prefill.cpp:4667-4677`）。backend ごとの「既定 share」の扱いは `arm_cpu_share` に別条件があります。CUDA 系では適格経路で未設定時の既定を arm し、HIP は gfx12 判定時のみ既定を arm します（`src/prefill/prefill.cpp:2845-2872`）。ただし `STRATA_PREFILL_CPU_SHARE_BATCH` はそれ自体を backend 制限で判定しません。

## 実行時の詳細

serve 初期化時に `share_batch` を読み、batch ありで有効なら stderr に `strata serve: STRATA_PREFILL_CPU_SHARE_BATCH=1: the prompt path may use the CPU pool beside the %lld batch slots, for a read with no slot decoding` という書式で出します（`src/program/generate.cpp:10121-10127`）。このログは利用可能性を示すもので、CPU share が各 read で実際に使われる保証ではありません。

batch prompt の各 read run 前に `share_gate` が slot の稼働数を調べ、`Prefill::set_share_blocked(busy > 0)` に渡します。有効設定時は最大4回、`strata batch: CPU share for this read: %s (%d slot(s) decoding)\n` の書式で stderr に出します（`src/program/generate.cpp:16477-16487,16596-16605`）。Prefill 側は chunk ごとに pool を取れるか確認し、条件を満たす場合に CPU pool へ非 resident expert の一部を割り当てます（`src/prefill/prefill.cpp:3571-3581,4667-4695,4804-4805`）。

share 用 pinned buffer を確保できない場合は、Strata はその engine の CPU share を停止して `prefill: the CPU share is off for this run: the host could not give %s (RAM is short); the GPU streams every expert\n` の書式で stderr に出します（`src/prefill/prefill.cpp:4669-4677`）。prefill のその他の失敗は通常の `Prefill::run` の失敗として呼び出し元へ返されます。本環境変数固有の終了・失敗経路はありません。

## 根拠

- 環境値の読み取り、pool の有効条件、起動ログ: `src/program/generate.cpp:10121-10135`。
- serve の Prefill への pool 設定: `src/program/generate.cpp:10629-10637`。
- batch slot 状態に応じた gate とログ: `src/program/generate.cpp:16477-16487,16596-16605,16908-16915`。
- pool と share の arm、backend の既定条件: `src/prefill/prefill.cpp:262-290,2844-2875`。
- chunk ごとの CPU share gate と適格条件・メモリ不足時の fallback: `src/prefill/prefill.cpp:3570-3581,4667-4695,4804-4805`。
