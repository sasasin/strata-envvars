# `STRATA_PF_PEER_OUT_PIPE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

peer GPU が計算した prompt の行を、グループ単位で primary GPU に戻す出力パイプラインを制御する目的の環境変数です。グループの計算と結果転送を別 stream / queue に分け、次のグループの計算と転送を重ねる経路に関係します。

ただし現 HEAD の `set_peer()` では、環境変数を判定する時点で `pp->compact` が構造体の初期値 `true` のままです。そのため通常の peer prefill 初期化では判定式が常に真となり、この環境変数の値を `0` にしても出力パイプラインは無効になりません。

## 値と判定

CUDA と SYCL の実装はどちらも `std::getenv()` で値を取得し、次の式を使います。

```cpp
(v == nullptr || std::atoi(v) != 0) || pp->compact
```

`std::atoi` は先頭の空白と符号を許し、先頭から読める10進整数を変換します。後ろに続く文字は判定に使われず、数字がない文字列や空文字は `0` として扱われます。

| 環境値 | 式の左側 | 最終的な `out_pipe`（通常の `set_peer()`） |
|---|---:|---:|
| 未設定 | 真 | 真 |
| `0`、`0suffix`、空文字、数字で始まらない文字列 | 偽 | 真（`pp->compact` が初期値 `true`） |
| `1`、`-1`、` 2tail` など `atoi` が非0を返す値 | 真 | 真 |

したがって、未設定時も `STRATA_PF_PEER_OUT_PIPE=0` の場合も実効値は同じです。`STRATA_PF_PEER_COMPACT` は後続で `pp->compact` を設定しますが、その設定より先に `out_pipe` が決まります。

## 有効になる条件

- `--peer-device` で有効な peer があり、`--peer-prefill-rows` が `0` でなく、peer prefill の `set_peer()` が呼ばれることが必要です。呼び出し側は peer が有効な場合に限って `set_peer()` を呼びます。
- peer prefill は MMQ prompt path を要求します。CUDA は P2P がない場合に mapped host route を使う設定を許す経路があります。SYCL 実装は P2P がない場合に初期化を拒否します。
- layer-split の stage helper 経路は `set_stage_helper()` で `out_pipe=true` と直接設定し、この環境変数を読みません。
- CUDA/SYCL の双方で `PeerPrefill::compact` はメンバー初期値が `true` です。CUDA ではその後 `STRATA_PF_PEER_COMPACT` の値または P2P 条件を反映し、SYCL では環境値を反映しますが、いずれも `STRATA_PF_PEER_OUT_PIPE` の判定後です。

## 実行時の詳細

この環境変数は `static` キャッシュではなく、peer prefill の初期化時に一度読み取られます。初期化後の環境変更は既に作られた `PeerPrefill` の設定を変えません。通常の `set_peer()` では前述の初期化順のため `out_pipe` が真になり、CUDA は第2 stream とグループ用 event を作成し、SYCL は出力 queue と event を作成します。作成に失敗すると peer の prompt buffer 初期化が失敗し、呼び出し側はstderr に `strata serve: %s - the prompt path stays on the primary GPU` と出して primary GPU に戻ります。

実行時、コンパクト経路ではグループごとの戻し転送が行われます。非コンパクト経路では `out_pipe` が真ならグループごとに転送を出力 stream / queue に積み、偽なら全行を計算 stream / queue からまとめて戻す分岐です。ところが通常の `set_peer()` では偽にできないため、まとめて戻す分岐はこの環境変数では選択できません。CUDA の `sums` 経路はグループごとの行ではなく重み付き和を返し、別の完了イベント処理を使うため、この変数による転送選択の影響を受けません。

この環境変数専用のログはありません。peer prefill が正常に初期化されると、CUDA は peer の行数や compact buffer 使用状況などを `strata prefill: peer GPU ...` として出しますが、`out_pipe` の値そのものは表示しません。

## 根拠

- `src/prefill/prefill.cpp:587-597,1649-1687,1695-1701`: CUDA の初期値、環境値判定、後続の compact 判定と resource 作成。
- `sycl/src/prefill/prefill.cpp:546-556,1689-1732,1751-1756`: SYCL の同じ判定順と初期値。
- `src/prefill/prefill.cpp:3587-3596,3650-3674`、`sycl/src/prefill/prefill.cpp:3643-3676,3737-3775`: グループ結果の転送と `out_pipe` による分岐。
- `src/program/generate.cpp:7368-7373`: peer が有効で `--peer-prefill-rows != 0` の場合に `set_peer()` を呼び、失敗時は primary GPU の prompt path に戻す処理。
- `docs/SECOND_GPU.md:131-148`: `--peer-device` と `--peer-prefill-rows` の一般的な説明。`STRATA_PF_PEER_OUT_PIPE` の値や判定順については説明していません。`docs/DETAILS.md` にもこの変数の説明は見当たりません。
