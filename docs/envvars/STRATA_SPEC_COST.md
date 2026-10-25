# `STRATA_SPEC_COST`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

MTP（multi-token prediction）を使う speculative decoding で、次の検証 window に含める draft 数を、draft の受理見込みと window の実測コストから選びます。従来の `--spec-min-p` による各 draft の確率しきい値で連鎖を止める代わりに、DraftPolicy が「各幅で期待できる確定 token 数 ÷ 検証コスト」を比較して、続けるかを逐次決めます。選ぶのは検証する draft の幅であり、この変数自体が draft token や verifier の判定を変更する処理はありません。

実装は server の生成ループと通常の `generate` ループにあります。server では engine の生成ループ初期化時、通常の generate では生成ループ初期化時に値を読みます。どちらもリクエストごとの再読込ではありません。server の DraftPolicy は複数リクエストをまたいで受理率とコストを学習します。

## 値と判定

両方の読み取り箇所とも `getenv()` の結果が存在し、先頭文字が `'1'` なら有効です。文字列全体の比較や数値 parse はしません。

| 値 | 判定 |
|---|---|
| unset | 無効 |
| 空文字 | 無効（値は存在するが先頭文字が `\0`） |
| `1`, `10`, `1anything` | 有効 |
| `0`, `true`, ` 1` など、先頭が `1` でない文字列 | 無効 |

大文字小文字、空白除去、数値としての妥当性確認はありません。起動後に環境を書き換えても、既に初期化された生成ループの判定には反映されません。

## 有効になる条件

- MTP が利用されるとき、生成ループに MTP の chain rule を登録し、各 draft の確率を受け取って次の draft を計算するか決めます。MTP を使わない場合はこの chain rule は登録されず、MTP window の選択にも使われません。ただし `DraftPolicy` の robust cost mode 自体は有効になるため、suffix draft (`--lookup`) がある場合はその窓選択にも影響し得ます。
- `--spec-min-p` が設定されていても、MTP の draft chain では登録済み chain rule がしきい値判定より優先されます。また、次の window 幅の決定も `STRATA_SPEC_COST` の `chain_rows` が優先されます。
- `--mtp-max-t` があれば上限は `min(--mtp-max-t, --spec)`、なければ `--spec` です。初回 window は専用の初回処理を行い、コストに基づく通常の幅選択は初回の後からです。残り context や VRAM による window 上限も適用されます。
- server の pipeline window 経路は独自の chain launch 処理を持ちます。ここで説明する逐次の chain rule/window 選択は、server の通常の逐次 decode loop に入った場合の挙動です。
- `STRATA_SPEC_COST_TABLE` が設定されていれば、`STRATA_SPEC_COST` が有効な場合に限り、起動時の初期コスト表として読み込みます。実測値で更新される初期値です。

## 実行時の詳細

1. `DraftPolicy` は `--spec` による最大幅で作られ、robust cost mode を有効にします。MTP がある場合は `MtpDrafter::set_chain_rule()` にコールバックを登録します。
2. draft ごとに、その draft の確率を受け取ります。Policy は確率 bucket ごとの実測受理率を用いて chain の期待確定 token 数を更新し、window 幅ごとの期待値をコストで割って比較します。次の幅が現在の最良幅を所定の margin だけ上回る見込みがある間、または未測定幅を試す条件を満たす間は chain を続けます。chain の上限に達した場合も最後の draft を Policy に通知します。
3. chain が終わると、記録した `chain_rows` を次の verify window の幅に使います。MTP の受理率は各 timed MTP round の結果から更新され、window コストも round 計測から更新されます。したがって、この状態は process 内で学習され、server ではリクエストをまたいで保持されます。
4. robust mode では、未測定幅の最初の graph capture round を通常のコスト標本として採用せず、他の幅から推定したコストを使います。幅に既知コストがある場合、極端に遅い標本は既知値の 2 倍を上限にして学習します。これは一時的な遅延や初回 capture によって幅が恒久的に選ばれなくなるのを避けるための Policy 内処理です。

有効時、通常の `generate` は終了時に `spec cost table` 行を stdout に出力します。serve の逐次 decode は同じ Policy を使いますが、この終了時出力は通常の generate loop のものです。

## 関連する `STRATA_SPEC_COST_TABLE`

この別変数はコスト-aware モードが有効な場合だけ参照され、空でない値を「コンテキスト長 `<6K`, `<24K`, `>=24K` の3群」に対応するセミコロン区切りリストとして読みます。各リストは窓幅1からのカンマ区切りミリ秒値です。実装は各要素を `atof` で変換し、正の値だけを空のコスト枠へ重み6で seed します。文字列全体の厳密な検証はなく、8幅を超える値と3群を超えるリストは採用されません。以後、実測コストが表を更新します。

## 根拠

- 値の読み取り、Policy 初期化、chain rule 登録: `src/program/generate.cpp:11177-11188`（serve）、`src/program/generate.cpp:16428-16453`（generate）。
- window 幅の適用と `--spec-min-p` との優先: `src/program/generate.cpp:14880-14889`（serve）、`src/program/generate.cpp:16531-16553`（generate）。
- chain rule と `min_p` 判定の選択、上限に達した場合の最終通知: `src/core/mtp.cpp:1685-1708`。
- コスト表の読み込み形式と seed 条件: `src/program/generate.cpp:16432-16447`、`src/spec/draft_policy.cpp:67-74`。
- robust mode の初回標本・外れ値処理、確率較正、幅選択の基準: `src/spec/draft_policy.cpp:55-65,154-173,182-223`。
- 通常 generate の終了時コスト表出力: `src/program/generate.cpp:16713-16715,16745`。
- `docs/DETAILS.md` と関連設計資料には、この環境変数によるコスト-aware MTP window の使用条件や測定値の説明を確認できませんでした。ここではソースコードで確認できる処理だけを記載しています。
