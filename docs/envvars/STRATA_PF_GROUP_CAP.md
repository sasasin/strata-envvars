# `STRATA_PF_GROUP_CAP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

`STRATA_PF_GROUP_CAP` は、prompt prefill の MMQ expert-group scratch 機能が使う、1 回に処理する expert 行数の上限を指定する内部調整値です。単独では機能を有効にしません。別の `STRATA_PF_GROUP_SCRATCH` が有効で、対象レイアウトが条件を満たす場合に、通常の cap 算出値をこの値で置き換えます。実装コメントは本変数を「test knob」としています。`src/prefill/prefill.cpp:1520-1528,1544-1550`。

## 値と判定

値は `std::getenv` で取得し、`std::atoll` で `int64_t` に変換します。文字列全体の妥当性確認やエラー報告はありません。

| 環境値 | `forced` | 適用される cap |
|---|---:|---:|
| 未設定 | 0 | 既定式 `ceil((T + 3 × avg) / 64) × 64`。ここで `avg = T × K × MMQ_GROUP / max(n_expert, 1)` |
| 空文字、数値に変換できない文字列、0、負数 | 0 以下 | 同じ既定式 |
| 正数 `x` | `x` | `max(x, T)` 行 |

`T` は chunk の token 数です。したがって指定値が正でも `T` より小さければ `T` 行に引き上げます。`atoll` の数値変換では先頭空白と符号を許し、数値の後ろにある文字列は検査されません（例: `128junk` は通常 128 として変換されます）。小数点表記は整数部分までの変換です。変換範囲外の値について、実装はエラー検査や fallback を明示していません。根拠: `src/prefill/prefill.cpp:1545-1550`。

## 有効になる条件

- `STRATA_PF_GROUP_SCRATCH` も設定され、`std::atoi(value) != 0` であること。未設定・空文字・数値変換が 0 になる値では無効、負数を含む非ゼロ整数は有効です。同スイッチの判定も最初の評価結果を `static` に保持します。`src/prefill/prefill.cpp:1526-1528`。
- prompt の MMQ 計画に MMQ 対象 layer があり、FP16 fallback / `pf_wmma` を使わず、全 layer が MMQ を使うこと。また `STRATA_MMQ_DIRECT` が layer で有効な場合は scratch 機能が拒否されます。条件を満たさない場合は stderr に `strata prefill: STRATA_PF_GROUP_SCRATCH=1 is ignored: ...` と理由を出し、本変数の cap は適用されません。`src/prefill/prefill.cpp:1529-1539`。
- scratch が有効でも fused buffer layout では `m.group_cap` を 0 にします。実行中に fused または FP16 経路へ入った場合は prefill が失敗し、`prefill: STRATA_PF_GROUP_SCRATCH needs MMQ on every layer (a layer took the fused or FP16 path)` を返します。`src/prefill/prefill.cpp:2064-2065,4542-4544`。

`docs/DETAILS.md:1087` は `STRATA_PF_GROUP_SCRATCH` を CUDA の prompt MMQ 経路向けとして記載しています。本変数自体の記述や異なる backend での挙動は資料にありません。今回確認した本変数の読み取りは `src/prefill/prefill.cpp` のみです。

## 実行時の詳細

cap は `group_cap_rows()` 内の関数ローカル `static const int64_t` で一度読み取られます。最初の評価後にプロセスの環境値を変えても再評価されません。scratch が有効で fused layout でない場合、`moe_bufs()` は GU/H/Hq scratch のサイズ計算に cap を使い、layout 初期化時に `m.group_cap` として保持します。chunk/layout の有効化ログは stderr に `strata prefill: chunk ... tokens: STRATA_PF_GROUP_SCRATCH on (GU/H/Hq hold <cap> rows, not <T×K>);` の形で出ます。`src/prefill/prefill.cpp:1585-1590,2064-2070`。

MMQ の 16 expert group の行数が cap を超える場合、コードは行数が cap 以下になる連続 expert の sub-range に分割し、各範囲の bounds を追加します。各範囲について gate/up、SwiGLU、q8_1 量子化、down の MMQ 処理を行います。bounds 表が容量を超えると `prefill: STRATA_PF_GROUP_SCRATCH's bounds table overflowed`、範囲が scratch 容量を超えると `prefill: STRATA_PF_GROUP_SCRATCH: a range of ... rows passes the scratch's ...` をエラーとして返します。bounds の GPU upload に失敗する経路では `prefill: the group bounds' upload failed` になります。`src/prefill/prefill.cpp:5037-5068,5662-5703`。

CLI 引数や設定ファイルから cap を上書きする処理は、この名前の全参照検索では見つかりませんでした。サーバーや子プロセスによる本変数の個別転送・上書きも確認できず、本実装は prefill を実行するプロセスの環境から直接読みます。

## 根拠

- 対象名の全参照: `src/prefill/prefill.cpp:1546-1548`（コメントと実際の `std::getenv` 読み取り）。他のコードでの直接参照はありません。
- 値、既定式、下限 clamp: `src/prefill/prefill.cpp:1545-1550`。
- 前提スイッチと対応条件: `src/prefill/prefill.cpp:1520-1539,2064-2070`。
- sub-range の生成、実行、失敗経路: `src/prefill/prefill.cpp:5037-5068,5662-5703`。
- 関連資料: `docs/DETAILS.md:1087`（`STRATA_PF_GROUP_SCRATCH` の説明。`STRATA_PF_GROUP_CAP` の値域や個別挙動は説明していません）。
