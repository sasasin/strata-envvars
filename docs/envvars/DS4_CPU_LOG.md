# `DS4_CPU_LOG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek-V4.1 (`ds4`) エンジンの CPU lane と Metal lookahead の診断集計を有効にします。主な出力は CPU lane 全体の呼び出し数・累積時間と、IQ 形式の CPU expert 計算を分けた累積フェーズ時間で、登録された `atexit` 関数から標準エラーへ出ます。macOS の IQ CPU lane ではページキャッシュの調査も有効になり、prefetch の実行経路が変わります。

これは CPU lane の計算方式や出力値を選ぶ設定ではありません。ただし macOS の IQ CPU lane では prefetch 経路を変えるので、その経路の計測時間に影響し得ます。

## 値と判定

`ds4_dbg(name)` は `STRATA_METAL` ビルドで `std::getenv(name) != nullptr` を返します。文字列の内容は parse しません。したがって未設定なら無効、空文字や `0` を含め何らかの値が設定されていれば有効です。比較、大文字小文字の扱い、数値の範囲検査はありません。CUDA/HIP など `STRATA_METAL` 以外のビルドでは helper が常に `false` を返すため、この変数による診断は有効になりません。

各判定は helper 呼び出し時に環境を参照し、`DS4_CPU_LOG` の判定値自体を static cache しません。実行中に環境を変更すれば後続の判定はその値を読みます。ただし集計値と `atexit` 登録状態は static で、終了時出力の登録後に変数を unset しても登録は取り消されません。

| 状態 | Metal | 非 Metal (CUDA/HIP 等) |
|---|---|---|
| 未設定 | 無効 | 常に無効 |
| 空文字 | 有効 | 常に無効 |
| `0`、`1`、その他の文字列 | 有効 | 常に無効 |

## 有効になる条件

- `DS4_CPU_LOG` の診断判定は `STRATA_METAL` が定義されたエンジンでのみ有効です。候補名の参照は `ds4` ソースと `docs/DEEPSEEK_MAC.md` にありますが、CUDA/HIP 側では `ds4_dbg` が compile-time の `false` です。
- CPU lane の呼び出しログは、レイヤーに host 側 expert (`ents`) がある経路で CPU 計算が行われる場合に記録されます。`DS4_SKIP_CPU` が有効なら CPU 計算は省略されるため、このログ計測箇所にも進みません。
- フェーズ別 `cpu_experts_iq` 集計は、CPU lane の形式が IQ 系である場合だけです。MXFP4 形式で `gg::mx_experts()` が真なら `cpu_experts_mx()` に進み、この IQ 専用集計は通りません。
- Metal lookahead 集計は lookahead の経路が呼ばれた場合に限ります。lookahead 自体は Metal の decode 経路で `T == 1` かつ `DS4_LOOKAHEAD` の深さが正の場合に試みられます。
- macOS ページキャッシュ集計と個別 prefetch は `__APPLE__` の IQ 経路で、`DS4_IQ_PF_COLD` による `pf_all` が真である場合に限ります。`DS4_IQ_PF_COLD` 未設定時は `pf_all` が真です。`DS4_CPU_LOG` が無効なら通常の一括または複数 worker の prefetch 分岐になります。

CLI 引数や設定ファイルによる `DS4_CPU_LOG` の上書きは見つかりません。別プロセスへの値の設定・転送もこの名前については見つかりません。

## 実行時の詳細

CPU lane が host expert を計算した場合、`DS4_CPU_LOG` が有効ならその呼び出しの経過時間を累積します。最初に有効状態で通った呼び出しで終了時処理を一度登録し、プロセス終了時に stderr へ `cpu lane calls: ...` を出します。内容は呼び出し数、処理した expert 数、累積 ms、1 呼び出し当たり ms、1 expert 当たり ms です。CPU lane の通常の計算と合成は `DS4_CPU_LOG` の有無にかかわらず行われます。

IQ CPU lane では、さらに prefetch、activation quantization、gate/up、down activation quantization、down の時間を個別に累積し、終了時に `cpu_experts_iq phases (ms over ... calls): ...` を stderr へ出します。計測は IQ 形式の expert 計算関数に入った呼び出しのみです。

macOS の IQ CPU lane で `pf_all` が真の場合、`DS4_CPU_LOG` が有効だと各 wanted matrix について `mincore()` で先頭最大 64 ページの resident 状態を調べ、行列ごとに `os::prefetch()` を実行して cold/warm の件数と時間を集計します。終了時に `prefetch: ... matrices cold ... warm ...` が stderr に出ます。この分岐はログだけでなく prefetch の単位・順序も変えます。`DS4_IQ_PF_COLD` が `0` と数値変換される値なら `pf_all` が偽となり、この分岐には入りません。

Metal lookahead 経路が実行されているときは CPU lane expert の予測ヒット数なども集計し、終了時に `lookahead: ...` を stderr へ出します。これらのログは実行中の各 token ごとに出るのではなく、終了時の累積値です。異常値による専用エラーや終了コードの変更はこの変数の読み取り箇所にはありません。

`docs/DEEPSEEK_MAC.md` は `DS4_CPU_LOG=1` を「per-token phase times」と紹介していますが、実装の該当ログは複数呼び出しを累積して終了時に出す形式です。また値判定は `=1` との一致ではなく、Metal では設定の有無です。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — Metal でのみ `getenv(name) != nullptr`、他 backend では常に false の共通 helper。
- `src/dsv41/ds4_model.cu:6455-6456,6626-6642` — IQ expert への形式 dispatch、IQ CPU lane の計時と終了時ログ登録。
- `src/dsv41/ds4_model.cu:6652-6680` — `DS4_IQ_PF_COLD` の既定値判定と、Apple 限定の `DS4_CPU_LOG` ページキャッシュ計測・prefetch 分岐。
- `src/dsv41/ds4_model.cu:6600-6604` — lookahead 集計の終了時ログ登録。
- `src/dsv41/ds4_model.cu:10432-10445` — Metal decode の `T == 1` / `DS4_LOOKAHEAD` 条件下で lookahead を試す経路。
- `src/dsv41/ds4_model.cu:10555-10580` — host expert がある場合の CPU lane 呼び出し、`DS4_SKIP_CPU` 分岐、累積ログ。
- `src/dsv41/ds4_model.cu:6816-6825` — CPU lane の形式 dispatch と `DS4_MISS_SPLIT` による経路分岐。
- `docs/DEEPSEEK_MAC.md:97` — 診断変数の説明。フェーズ粒度の表現は実装の終了時累積ログとは一致しません。
